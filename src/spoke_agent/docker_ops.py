"""Duenne Wrappers um ``docker compose`` und ``docker``.

Wir sprechen Docker exklusiv ueber subprocess + den im Container gemounteten
``/var/run/docker.sock`` an. Keine SDK-Abhaengigkeit (vereinfacht das Image,
braucht aber Docker-CLI im Container — wird im Dockerfile installiert).

Alle Calls sind async (subprocess.exec) und haben ein Timeout.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Sequence

log = logging.getLogger(__name__)


class DockerError(RuntimeError):
    """Fehler beim Aufruf von docker/docker compose."""


async def _run(cmd: Sequence[str], timeout: float = 30.0) -> tuple[int, str, str]:
    if not shutil.which(cmd[0]):
        raise DockerError(f"binary not found: {cmd[0]}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise DockerError(f"spawn failed: {exc}") from exc
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise DockerError(f"timeout after {timeout}s: {' '.join(cmd[:3])}") from exc
    return proc.returncode or 0, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")


def _compose_args(compose_path: str) -> list[str]:
    return ["docker", "compose", "-f", compose_path]


async def compose_restart(compose_path: str, service: str) -> str:
    rc, out, err = await _run([*_compose_args(compose_path), "restart", service], timeout=120.0)
    if rc != 0:
        raise DockerError(err.strip() or out.strip() or "compose restart failed")
    return (out + err).strip()


async def compose_stop(compose_path: str, service: str) -> str:
    rc, out, err = await _run([*_compose_args(compose_path), "stop", service], timeout=60.0)
    if rc != 0:
        raise DockerError(err.strip() or out.strip() or "compose stop failed")
    return (out + err).strip()


async def compose_start(compose_path: str, service: str) -> str:
    rc, out, err = await _run([*_compose_args(compose_path), "start", service], timeout=60.0)
    if rc != 0:
        # ``compose start`` greift nur wenn der Container existiert. Wenn er
        # weg ist, mit ``up -d`` neu erzeugen.
        rc2, out2, err2 = await _run(
            [*_compose_args(compose_path), "up", "-d", service],
            timeout=120.0,
        )
        if rc2 != 0:
            raise DockerError(err2.strip() or out2.strip() or "compose up failed")
        return (out2 + err2).strip()
    return (out + err).strip()


async def compose_pull_up(compose_path: str, service: str | None = None) -> str:
    args = [*_compose_args(compose_path), "pull"]
    if service and service != "all":
        args.append(service)
    rc, out, err = await _run(args, timeout=600.0)
    if rc != 0:
        raise DockerError(err.strip() or out.strip() or "compose pull failed")

    args2 = [*_compose_args(compose_path), "up", "-d"]
    if service and service != "all":
        args2.append(service)
    rc2, out2, err2 = await _run(args2, timeout=300.0)
    if rc2 != 0:
        raise DockerError(err2.strip() or out2.strip() or "compose up failed")
    return (out + err + out2 + err2).strip()


async def docker_logs(service: str, tail: int = 200) -> list[str]:
    rc, out, err = await _run(
        ["docker", "logs", "--tail", str(tail), service], timeout=10.0
    )
    if rc != 0:
        if "No such container" in err:
            return [f"<no container: {service}>"]
        raise DockerError(err.strip() or out.strip() or "docker logs failed")
    combined = (out + err).splitlines()
    return combined[-tail:]


async def docker_logs_stream(service: str, lines: int = 50):
    """Async-Generator fuer Live-Logs.

    Aufrufer ist verantwortlich, die Subprocess sauber zu schliessen
    (cancel + proc.kill).
    """
    cmd = ["docker", "logs", "--tail", str(lines), "-f", service]
    if not shutil.which(cmd[0]):
        yield f"<docker not installed: cannot stream {service}>"
        return
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            yield raw.decode("utf-8", errors="replace").rstrip("\n")
    finally:
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
