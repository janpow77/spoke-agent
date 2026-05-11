"""Service- und Hardware-Discovery.

- HTTP-Probes auf bekannte Ports (ollama 11434, reranker 8004, vision 8005)
- GPU-Erkennung:
    Linux/NVIDIA  → ``nvidia-smi --query-gpu=...``
    macOS         → ``system_profiler SPDisplaysDataType``
    sonst         → ``None`` (CPU-only)
- Docker-Container-Korrelation: ``docker ps --filter name=<svc>``

Alle Subprocess-Aufrufe sind defensiv (Timeout + try/except), damit eine
fehlende Binary den Loop nicht abreissen laesst.
"""
from __future__ import annotations

import asyncio
import json
import logging
import platform
import shutil
import socket
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import SpokeAgentConfig
from .models import DiscoverySnapshot, GpuInfo, HostInfo, ServiceInfo

log = logging.getLogger(__name__)


# ----------------------------- GPU ----------------------------------------


async def detect_gpu() -> GpuInfo | None:
    """Liefert einen GPU-Snapshot oder ``None`` wenn keine GPU verfuegbar."""
    system = platform.system()
    if system == "Linux":
        nv = await _detect_nvidia()
        if nv is not None:
            return nv
        return await _detect_rocm()
    if system == "Darwin":
        return await _detect_apple_metal()
    return None


async def _detect_nvidia() -> GpuInfo | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=3.0)
    except (TimeoutError, FileNotFoundError, OSError) as exc:
        log.debug("nvidia-smi nicht ausfuehrbar: %s", exc)
        return None
    if proc.returncode != 0:
        return None
    first = (out.decode("utf-8", errors="replace") or "").strip().splitlines()
    if not first:
        return None
    parts = [p.strip() for p in first[0].split(",")]
    if len(parts) < 4:
        return None
    try:
        return GpuInfo(
            device=parts[0],
            vram_total_mb=int(parts[1]),
            vram_used_mb=int(parts[2]),
            util_pct=float(parts[3]),
        )
    except (ValueError, IndexError):
        return None


async def _detect_rocm() -> GpuInfo | None:
    """Detection fuer AMD-GPUs mit ROCm.

    Bevorzugt rocm-smi (gibt VRAM-Daten als JSON aus). Fallback rocminfo
    (nur Name + gfx-Version, ohne VRAM-Util). Auf APUs wie Strix Halo
    ist VRAM-Total = shared system RAM Anteil — wir reporten was ROCm sagt.
    """
    if shutil.which("rocm-smi"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi", "--showmeminfo", "vram", "--showuse", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _err = await asyncio.wait_for(proc.communicate(), timeout=3.0)
            if proc.returncode == 0:
                try:
                    data = json.loads(out.decode("utf-8", errors="replace") or "{}")
                    cards = [v for k, v in data.items() if k.startswith("card")]
                    if cards:
                        first = cards[0]
                        vram_total = first.get("VRAM Total Memory (B)") or first.get("vram_total")
                        vram_used = first.get("VRAM Total Used Memory (B)") or first.get("vram_used")
                        util = first.get("GPU use (%)") or first.get("util_pct") or 0
                        return GpuInfo(
                            device=str(first.get("Card series") or first.get("name") or "AMD GPU"),
                            vram_total_mb=int(int(vram_total) / (1024 * 1024)) if vram_total else None,
                            vram_used_mb=int(int(vram_used) / (1024 * 1024)) if vram_used else None,
                            util_pct=float(util) if util else 0.0,
                        )
                except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
                    log.debug("rocm-smi json parse failed: %s", exc)
        except (TimeoutError, FileNotFoundError, OSError) as exc:
            log.debug("rocm-smi not runnable: %s", exc)
    # Fallback: rocminfo gives at least name + gfx-version, no VRAM
    if not shutil.which("rocminfo"):
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "rocminfo",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=3.0)
    except (TimeoutError, FileNotFoundError, OSError):
        return None
    text = out.decode("utf-8", errors="replace") if out else ""
    if "gfx" not in text:
        return None
    import re
    gfx_match = re.search(r"gfx[0-9]+", text)
    name_match = re.search(r"Marketing Name:\s*(.+)", text)
    gfx = gfx_match.group(0) if gfx_match else None
    name = name_match.group(1).strip() if name_match else (f"AMD {gfx}" if gfx else "AMD GPU")
    return GpuInfo(device=name)


async def _detect_apple_metal() -> GpuInfo | None:
    if not shutil.which("system_profiler"):
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "system_profiler", "SPDisplaysDataType", "-json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    except (TimeoutError, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(out.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return None
    displays = data.get("SPDisplaysDataType") or []
    if not displays:
        return None
    first = displays[0]
    name = first.get("sppci_model") or first.get("_name") or "Apple GPU"
    vram_raw = first.get("spdisplays_vram") or first.get("spdisplays_vram_shared")
    vram_mb: int | None = None
    if isinstance(vram_raw, str):
        # "16 GB" / "8192 MB"
        tokens = vram_raw.split()
        try:
            n = int(tokens[0])
            if "gb" in vram_raw.lower():
                vram_mb = n * 1024
            else:
                vram_mb = n
        except ValueError:
            vram_mb = None
    return GpuInfo(device=str(name), vram_total_mb=vram_mb)


# ----------------------------- Service-Probes -----------------------------


async def probe_service(client: httpx.AsyncClient, svc: dict) -> ServiceInfo:
    """HTTP-Probe gegen einen einzelnen Service.

    Verwendet GET <base_url><health_path>. Status:
    - ``ok``           → 2xx innerhalb 3s
    - ``unreachable``  → Netzwerkfehler (Connection refused etc.)
    - ``down``         → erreichbar, aber Non-2xx
    """
    name = svc["name"]
    url = svc["url"]
    health_path = svc.get("health_path", "/health")
    info = ServiceInfo(
        name=name,
        type=svc.get("type", "custom"),
        base_url=url,
        capabilities=list(svc.get("capabilities", [])),
        compose_service=svc.get("compose_service") or name,
        last_check_at=datetime.now(UTC),
    )
    target = f"{url.rstrip('/')}{health_path}"
    try:
        resp = await client.get(target, timeout=3.0)
        if resp.status_code < 300:
            info.status = "ok"
            # Version-Extraktion (best effort)
            try:
                body = resp.json()
                if isinstance(body, dict):
                    info.version = (
                        body.get("version")
                        or body.get("build")
                        or (body.get("data") or {}).get("version")  # type: ignore[union-attr]
                    )
            except Exception:
                pass
        else:
            info.status = "down"
            info.last_error = f"HTTP {resp.status_code}"
    except httpx.RequestError as exc:
        info.status = "unreachable"
        info.last_error = type(exc).__name__
    except Exception as exc:  # noqa: BLE001
        info.status = "unreachable"
        info.last_error = str(exc)[:200]
    return info


async def annotate_docker(info: ServiceInfo) -> ServiceInfo:
    """Reichert ``info`` mit Docker-Container-Daten an (falls Docker-Sock da)."""
    if not shutil.which("docker"):
        return info
    name = info.compose_service or info.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "-a",
            "--filter", f"name=^/{name}$",
            "--format", "{{json .}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=3.0)
    except (TimeoutError, FileNotFoundError, OSError):
        return info
    if proc.returncode != 0:
        return info
    line = (out.decode("utf-8", errors="replace") or "").strip().splitlines()
    if not line:
        return info
    try:
        record = json.loads(line[0])
    except json.JSONDecodeError:
        return info
    info.container_id = record.get("ID")
    info.container_state = record.get("State") or record.get("Status")
    # docker inspect — image digest
    try:
        proc2 = await asyncio.create_subprocess_exec(
            "docker", "inspect", "--format={{.Image}}", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out2, _err2 = await asyncio.wait_for(proc2.communicate(), timeout=2.0)
        if proc2.returncode == 0:
            digest = (out2.decode("utf-8", errors="replace") or "").strip()
            if digest:
                info.image_digest = digest.split(":")[-1][:12] if ":" in digest else digest[:12]
    except Exception:
        pass
    return info


# ----------------------------- Host-Info -----------------------------------


def host_info() -> HostInfo:
    return HostInfo(
        hostname=socket.gethostname(),
        platform=platform.system().lower(),
        arch=platform.machine(),
        kernel=platform.release(),
        container_runtime="docker" if shutil.which("docker") else None,
    )


# ----------------------------- Snapshot-Aggregation -----------------------


async def discover(cfg: SpokeAgentConfig) -> DiscoverySnapshot:
    snapshot = DiscoverySnapshot(host_info=host_info(), refreshed_at=datetime.now(UTC))
    async with httpx.AsyncClient(timeout=3.0) as client:
        tasks = [probe_service(client, svc) for svc in cfg.services]
        infos: list[ServiceInfo] = await asyncio.gather(*tasks, return_exceptions=False)
    enriched: list[ServiceInfo] = []
    for info in infos:
        try:
            enriched.append(await annotate_docker(info))
        except Exception as exc:  # noqa: BLE001
            log.debug("annotate_docker(%s) failed: %s", info.name, exc)
            enriched.append(info)
    snapshot.services = enriched
    snapshot.gpu = await detect_gpu()
    caps: set[str] = set()
    for s in enriched:
        if s.status == "ok":
            caps.update(s.capabilities)
    snapshot.capabilities = sorted(caps)
    return snapshot


# ----------------------------- ENV-Sniffing -------------------------------
# Welche ENVs werden pro Service als "editierbar" exponiert? Hard-codiert,
# damit die UI ohne Schema-Discovery weiss, was sie anzeigen soll.

SERVICE_EDITABLE_ENV: dict[str, list[str]] = {
    "ollama": ["OLLAMA_KEEP_ALIVE", "OLLAMA_NUM_PARALLEL", "OLLAMA_FLASH_ATTENTION", "OLLAMA_HOST"],
    "reranker-service": [
        "RERANKER_DEVICE",
        "RERANKER_DEFAULT_MODEL",
        "RERANKER_PRELOAD_MODELS",
        "RERANKER_MAX_PASSAGES",
        "RERANKER_MAX_SEQ_LEN",
        "RERANKER_API_KEY",
    ],
    "vision-service": [
        "VISION_DEVICE",
        "VISION_DEFAULT_MODEL",
        "VISION_API_KEY",
    ],
}


async def read_service_env(service: str) -> dict[str, str]:
    """Liest ENVs eines Containers via ``docker inspect``.

    Wenn der Container nicht laeuft (oder Docker nicht erreichbar): leeres Dict.
    """
    if not shutil.which("docker"):
        return {}
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "--format={{json .Config.Env}}", service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=3.0)
    except (TimeoutError, FileNotFoundError, OSError):
        return {}
    if proc.returncode != 0:
        return {}
    try:
        env_list = json.loads(out.decode("utf-8", errors="replace") or "[]")
    except json.JSONDecodeError:
        return {}
    parsed: dict[str, str] = {}
    for entry in env_list or []:
        if "=" in entry:
            k, v = entry.split("=", 1)
            parsed[k] = v
    editable = set(SERVICE_EDITABLE_ENV.get(service, []))
    # nur editierbare zurueckgeben — verhindert dass Secrets aus dem
    # Container-Umfeld an die UI leaken.
    return {k: v for k, v in parsed.items() if k in editable}


def discovery_to_dict(snapshot: DiscoverySnapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")
