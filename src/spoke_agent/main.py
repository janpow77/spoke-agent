"""FastAPI-App des Spoke-Agents.

Routen unter ``/api/*`` (kein ``/admin``-Prefix — der Agent ist eine
Single-Purpose-App, keine Multi-Tenant-Console).

Endpoints:
- GET    /health
- POST   /api/auth/login                  -> Login (Token)
- POST   /api/auth/logout                 -> Token revoke
- GET    /api/auth/me                     -> Session-Info
- GET    /api/status                      -> Status + Discovery + Router
- GET    /api/services                    -> Pro Service: status, version, ...
- POST   /api/services/{name}/restart
- POST   /api/services/{name}/stop
- POST   /api/services/{name}/start
- GET    /api/services/{name}/logs        -> tail=N
- GET    /api/services/{name}/config
- PUT    /api/services/{name}/config
- GET    /api/router                      -> Router-Status
- PUT    /api/router                      -> Router-Konfig aendern
- POST   /api/update                      -> compose pull + up -d
- WS     /api/logs/stream                 -> Live-Logs aller Services
- GET    /admin/*                         -> Vue 3 SPA (vom Build-Output)

Die SPA liegt im Container unter ``/app/frontend_dist``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import _auth_disabled, issue_token, require_auth, revoke_token
from .config import SpokeAgentConfig, load_config
from .config_store import apply_overrides, load_overrides, set_override
from .discovery import SERVICE_EDITABLE_ENV, discover, read_service_env
from .docker_ops import (
    DockerError,
    compose_pull_up,
    compose_restart,
    compose_start,
    compose_stop,
    docker_logs,
    docker_logs_stream,
)
from .models import (
    AgentStatus,
    DiscoverySnapshot,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RouterConfig,
    RouterStatus,
    ServiceConfigResponse,
    ServiceConfigUpdate,
    ServiceInfo,
    ServiceLogResponse,
    UpdateRequest,
)
from .registration import registration_loop

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)
log = logging.getLogger("spoke-agent")


# ----------------------------- App-State ----------------------------------

_APP_STATE: dict = {
    "started_at": 0.0,
    "config": None,
    "stop_event": None,
    "last_snapshot": None,
    "registrar": None,
}


def get_config() -> SpokeAgentConfig:
    cfg = _APP_STATE.get("config")
    if cfg is None:
        cfg = load_config()
        apply_overrides(cfg, load_overrides(cfg.state_dir))
        _APP_STATE["config"] = cfg
    return cfg


def reload_config() -> SpokeAgentConfig:
    cfg = load_config()
    apply_overrides(cfg, load_overrides(cfg.state_dir))
    _APP_STATE["config"] = cfg
    return cfg


# ----------------------------- Lifespan -----------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = reload_config()
    Path(cfg.state_dir).mkdir(parents=True, exist_ok=True)
    log.info(
        "spoke-agent %s startet — spoke=%s router=%s services=%d auth=%s",
        __version__,
        cfg.spoke_name,
        cfg.router_url,
        len(cfg.services),
        "off" if _auth_disabled() else "on",
    )
    _APP_STATE["started_at"] = time.time()
    _APP_STATE["stop_event"] = asyncio.Event()
    # Erste Discovery sofort fuer schnellen UI-Start
    try:
        _APP_STATE["last_snapshot"] = await discover(cfg)
    except Exception as exc:  # noqa: BLE001
        log.warning("Erste Discovery fehlgeschlagen: %s", exc)

    reg_task = asyncio.create_task(
        registration_loop(get_config, _APP_STATE, _APP_STATE["stop_event"]),
    )
    _APP_STATE["registration_task"] = reg_task

    try:
        yield
    finally:
        _APP_STATE["stop_event"].set()
        try:
            await asyncio.wait_for(reg_task, timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            reg_task.cancel()
        log.info("spoke-agent stoppt.")


app = FastAPI(
    title="spoke-agent",
    version=__version__,
    description="Pro-Host-Agent fuer Service-Discovery + Router-Anbindung.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------- Health -------------------------------------


@app.get("/health")
async def health() -> dict:
    started = _APP_STATE.get("started_at") or time.time()
    cfg = get_config()
    registrar = _APP_STATE.get("registrar")
    return {
        "status": "ok",
        "version": __version__,
        "spoke_name": cfg.spoke_name,
        "uptime_s": int(time.time() - started),
        "router_connected": bool(getattr(getattr(registrar, "status", None), "connected", False)),
    }


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/")


@app.exception_handler(Exception)
async def unhandled_exception(_request, exc: Exception):
    log.exception("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"error": "internal", "detail": str(exc)[:200]})


# ----------------------------- Auth ---------------------------------------


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    cfg = get_config()
    # Konstante Vergleichszeit
    import hmac

    if not hmac.compare_digest(payload.password or "", cfg.admin_password):
        raise HTTPException(status_code=401, detail="Wrong password")
    session = issue_token()
    return LoginResponse(
        token=session.token,
        expires_at=datetime.fromtimestamp(session.expires_at_epoch, tz=UTC),
    )


@app.post("/api/auth/logout")
async def logout(request: Request) -> dict:
    h = request.headers.get("authorization") or ""
    if h.lower().startswith("bearer "):
        revoke_token(h.split(" ", 1)[1].strip())
    return {"ok": True}


@app.get("/api/auth/me", response_model=MeResponse)
async def me(request: Request) -> MeResponse:
    if _auth_disabled():
        return MeResponse(logged_in=True, expires_at=datetime.now(UTC) + timedelta(days=365))
    h = request.headers.get("authorization") or ""
    if not h.lower().startswith("bearer "):
        return MeResponse(logged_in=False)
    try:
        s = require_auth(request)
    except HTTPException:
        return MeResponse(logged_in=False)
    if s is None:
        return MeResponse(logged_in=True)
    return MeResponse(
        logged_in=True,
        expires_at=datetime.fromtimestamp(s.expires_at_epoch, tz=UTC),
    )


# ----------------------------- Status -------------------------------------


def _build_router_status() -> RouterStatus:
    cfg = get_config()
    registrar = _APP_STATE.get("registrar")
    if registrar is not None:
        return registrar.status
    return RouterStatus(url=cfg.router_url, fallback_url=cfg.fallback_router_url, app_id=cfg.app_id)


def _current_snapshot() -> DiscoverySnapshot:
    snap = _APP_STATE.get("last_snapshot")
    if isinstance(snap, DiscoverySnapshot):
        return snap
    return DiscoverySnapshot()


@app.get("/api/status", response_model=AgentStatus)
async def api_status(_=Depends(require_auth)) -> AgentStatus:
    cfg = get_config()
    started = _APP_STATE.get("started_at") or time.time()
    return AgentStatus(
        spoke_name=cfg.spoke_name,
        spoke_tags=cfg.spoke_tags,
        version=__version__,
        uptime_s=int(time.time() - started),
        discovery=_current_snapshot(),
        router=_build_router_status(),
    )


# ----------------------------- Services -----------------------------------


def _find_service(name: str) -> ServiceInfo:
    snap = _current_snapshot()
    for s in snap.services:
        if s.name == name:
            return s
    cfg = get_config()
    for svc in cfg.services:
        if svc["name"] == name:
            return ServiceInfo(
                name=svc["name"],
                type=svc.get("type", "custom"),
                base_url=svc["url"],
                capabilities=list(svc.get("capabilities", [])),
                compose_service=svc.get("compose_service") or svc["name"],
            )
    raise HTTPException(status_code=404, detail=f"Service '{name}' unknown")


@app.get("/api/services", response_model=list[ServiceInfo])
async def api_services_list(_=Depends(require_auth)) -> list[ServiceInfo]:
    return _current_snapshot().services


@app.post("/api/services/refresh")
async def api_services_refresh(_=Depends(require_auth)) -> DiscoverySnapshot:
    snap = await discover(get_config())
    _APP_STATE["last_snapshot"] = snap
    return snap


@app.post("/api/services/{name}/restart")
async def api_service_restart(name: str, _=Depends(require_auth)) -> dict:
    svc = _find_service(name)
    cfg = get_config()
    try:
        out = await compose_restart(cfg.docker_compose_path, svc.compose_service or name)
    except DockerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "log": out}


@app.post("/api/services/{name}/stop")
async def api_service_stop(name: str, _=Depends(require_auth)) -> dict:
    svc = _find_service(name)
    cfg = get_config()
    try:
        out = await compose_stop(cfg.docker_compose_path, svc.compose_service or name)
    except DockerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "log": out}


@app.post("/api/services/{name}/start")
async def api_service_start(name: str, _=Depends(require_auth)) -> dict:
    svc = _find_service(name)
    cfg = get_config()
    try:
        out = await compose_start(cfg.docker_compose_path, svc.compose_service or name)
    except DockerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "log": out}


@app.get("/api/services/{name}/logs", response_model=ServiceLogResponse)
async def api_service_logs(
    name: str,
    tail: int = Query(200, ge=1, le=2000),
    _=Depends(require_auth),
) -> ServiceLogResponse:
    svc = _find_service(name)
    try:
        lines = await docker_logs(svc.compose_service or name, tail=tail)
    except DockerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ServiceLogResponse(service=name, lines=lines, tail=tail)


@app.get("/api/services/{name}/config", response_model=ServiceConfigResponse)
async def api_service_config_get(name: str, _=Depends(require_auth)) -> ServiceConfigResponse:
    svc = _find_service(name)
    editable = SERVICE_EDITABLE_ENV.get(svc.compose_service or name, [])
    env = await read_service_env(svc.compose_service or name)
    return ServiceConfigResponse(service=name, env=env, editable_keys=editable)


@app.put("/api/services/{name}/config", response_model=ServiceConfigResponse)
async def api_service_config_put(
    name: str, payload: ServiceConfigUpdate, _=Depends(require_auth),
) -> ServiceConfigResponse:
    """Persistiert ENVs in einer Service-spezifischen .env-Datei.

    Pfad: ``$state_dir/services/<name>.env`` — die Compose-Datei sollte diese
    Datei via ``env_file:`` einbinden. Nach dem Schreiben triggern wir
    automatisch einen ``compose up -d <name>`` damit die neuen Werte greifen.
    """
    svc = _find_service(name)
    cfg = get_config()
    editable = set(SERVICE_EDITABLE_ENV.get(svc.compose_service or name, []))
    if not editable:
        raise HTTPException(status_code=400, detail="Service has no editable env keys")

    rejected = [k for k in payload.env.keys() if k not in editable]
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=f"Not editable: {', '.join(rejected)}",
        )

    env_dir = Path(cfg.state_dir) / "services"
    env_dir.mkdir(parents=True, exist_ok=True)
    env_file = env_dir / f"{svc.compose_service or name}.env"

    # Best-effort merge: bestehende Datei lesen, ueberschreiben, fertig.
    existing: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v
    existing.update(payload.env)

    body = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    env_file.write_text(body, encoding="utf-8")
    try:
        os.chmod(env_file, 0o600)
    except Exception:
        pass

    # Auto-Apply: compose up -d <name>
    try:
        await compose_pull_up(cfg.docker_compose_path, svc.compose_service or name)
    except DockerError as exc:
        log.warning("compose up -d nach Config-Update fehlgeschlagen: %s", exc)

    return await api_service_config_get(name)  # frischer Read


# ----------------------------- Router-Config ------------------------------


@app.get("/api/router", response_model=RouterStatus)
async def api_router(_=Depends(require_auth)) -> RouterStatus:
    return _build_router_status()


@app.put("/api/router", response_model=RouterStatus)
async def api_router_put(payload: RouterConfig, _=Depends(require_auth)) -> RouterStatus:
    cfg = get_config()
    changes: dict[str, object] = {}
    if payload.url is not None:
        changes["router_url"] = payload.url.rstrip("/")
    if payload.fallback_url is not None:
        changes["fallback_router_url"] = payload.fallback_url.rstrip("/") or None
    if payload.api_key is not None:
        changes["api_key"] = payload.api_key
    if payload.registration_token is not None:
        changes["registration_token"] = payload.registration_token
    if payload.spoke_tags is not None:
        changes["spoke_tags"] = list(payload.spoke_tags)

    for k, v in changes.items():
        set_override(cfg.state_dir, k, v)

    reload_config()
    return _build_router_status()


# ----------------------------- Update -------------------------------------


@app.post("/api/update")
async def api_update(payload: UpdateRequest | None = None, _=Depends(require_auth)) -> dict:
    cfg = get_config()
    service = "all"
    if payload and payload.service:
        service = payload.service
    try:
        out = await compose_pull_up(cfg.docker_compose_path, service if service != "all" else None)
    except DockerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "log": out}


# ----------------------------- Live-Logs via WebSocket --------------------


@app.websocket("/api/logs/stream")
async def ws_logs(ws: WebSocket, service: str | None = None) -> None:
    """Live-Multi-Service-Log-Stream.

    Auth: Bearer-Token via Query (?token=...) oder Subprotocol. Auf einem
    Tailscale-only Deployment laesst sich Auth via SPOKE_AGENT_AUTH=off
    komplett abschalten — die WS-Route respektiert das.
    """
    await ws.accept()
    if not _auth_disabled():
        token = ws.query_params.get("token") or ""
        from .auth import _SESSIONS

        s = _SESSIONS.get(token)
        if not s or s.expires_at_epoch < time.time():
            await ws.close(code=4401, reason="unauthorized")
            return

    cfg = get_config()
    services = (
        [service] if service else [s["compose_service"] or s["name"] for s in cfg.services]
    )

    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1024)

    async def pump(name: str) -> None:
        try:
            async for line in docker_logs_stream(name, lines=50):
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                await queue.put({"service": name, "line": line})
        except Exception as exc:  # noqa: BLE001
            await queue.put({"service": name, "line": f"<stream-error: {exc}>"})

    tasks = [asyncio.create_task(pump(name)) for name in services]
    try:
        while True:
            msg = await queue.get()
            await ws.send_text(json.dumps(msg))
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass


# ----------------------------- SPA ----------------------------------------


_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend_dist"


def _mount_spa() -> None:
    if not (_FRONTEND_DIR / "index.html").exists():
        log.warning(
            "Admin-Frontend nicht gefunden unter %s — UI nicht verfuegbar", _FRONTEND_DIR,
        )
        return

    if (_FRONTEND_DIR / "assets").exists():
        app.mount(
            "/admin/assets",
            StaticFiles(directory=_FRONTEND_DIR / "assets"),
            name="spoke-agent-assets",
        )

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/", include_in_schema=False)
    async def _admin_root():
        return FileResponse(_FRONTEND_DIR / "index.html")

    @app.get("/admin/{full_path:path}", include_in_schema=False)
    async def _admin_spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = _FRONTEND_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIR / "index.html")


_mount_spa()
