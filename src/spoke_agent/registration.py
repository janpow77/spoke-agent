"""Registrierungs-Loop fuer den zentralen llm-router.

Alle ``register_interval_s`` Sekunden:
1. Discovery aktualisieren
2. ``POST <router>/admin/api/spokes/register`` mit Status-Payload schicken
3. Bei Erfolg: ``RouterStatus`` aktualisieren
4. Bei Fehler: exponential backoff (Cap = ``max_backoff_s``)
5. Nach ``fallback_after_failures`` aufeinanderfolgenden Failures auf
   ``fallback_router_url`` umschalten (falls konfiguriert)
6. Bei erneuter Verbindung re-register vollstaendig (Router koennte
   zwischenzeitlich neugestartet haben).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from . import __version__
from .config import SpokeAgentConfig
from .discovery import discover
from .models import DiscoverySnapshot, RouterStatus, ServiceInfo, SpokeRegisterPayload

log = logging.getLogger(__name__)


# ---- Endpoint-Pfade ------------------------------------------------------
# Wir POSTen primaer gegen "/admin/api/spokes/register"  (vom parallelen
# Router-Agenten neu eingefuehrt). Falls dieser Endpoint nicht existiert,
# faellt der Loop auf ``/admin/api/spokes`` (legacy CRUD) zurueck.
PRIMARY_PATH = "/admin/api/spokes/register"
LEGACY_PATH = "/admin/api/spokes"


def _payload_from_snapshot(
    cfg: SpokeAgentConfig,
    snapshot: DiscoverySnapshot,
) -> SpokeRegisterPayload:
    base_url = f"http://{snapshot.host_info.hostname or cfg.spoke_name}:{cfg.bind_port}"
    return SpokeRegisterPayload(
        name=cfg.spoke_name,
        base_url=base_url,
        type="spoke-agent",
        capabilities=snapshot.capabilities,
        tags=cfg.spoke_tags,
        priority=100,
        gpu_info=snapshot.gpu,
        services=snapshot.services,
        host_info=snapshot.host_info,
        source="dynamic",
        fallback_url=cfg.fallback_router_url,
        enabled=True,
    )


def _serialize(payload: SpokeRegisterPayload) -> dict[str, Any]:
    return payload.model_dump(mode="json", exclude_none=False)


async def _post_register(
    client: httpx.AsyncClient,
    base: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[bool, int, str]:
    url = f"{base.rstrip('/')}{path}"
    try:
        resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
    except httpx.RequestError as exc:
        return False, 0, f"{type(exc).__name__}: {exc}"
    if resp.status_code < 300:
        return True, resp.status_code, ""
    return False, resp.status_code, (resp.text or "")[:200]


class Registrar:
    """Verwaltet Registrar-Status + Connection-Tracking.

    Stateful, weil wir Backoff/Fallback-Switch ueber mehrere Iterationen
    hinweg verfolgen muessen.
    """

    def __init__(self, cfg: SpokeAgentConfig, state: dict[str, Any]) -> None:
        self.cfg = cfg
        self.state = state
        self.status = RouterStatus(
            url=cfg.router_url,
            fallback_url=cfg.fallback_router_url,
            app_id=cfg.app_id,
        )
        self._current_path = PRIMARY_PATH
        self._last_was_failure = True  # initial: noch nie verbunden
        self._backoff_s = cfg.register_interval_s

    def update_config(self, cfg: SpokeAgentConfig) -> None:
        self.cfg = cfg
        self.status.url = cfg.router_url
        self.status.fallback_url = cfg.fallback_router_url
        self.status.app_id = cfg.app_id
        # Bei Konfig-Aenderung: sofortige Re-Registrierung im naechsten Tick.
        self.status.consecutive_failures = 0
        self._last_was_failure = True
        self._backoff_s = cfg.register_interval_s

    def _active_base_url(self) -> str:
        if self.status.using_fallback and self.cfg.fallback_router_url:
            return self.cfg.fallback_router_url
        return self.cfg.router_url

    def _headers(self) -> dict[str, str]:
        h = {"User-Agent": f"spoke-agent/{__version__}", "Content-Type": "application/json"}
        if self.cfg.registration_token:
            h["X-Spoke-Token"] = self.cfg.registration_token
        if self.cfg.api_key:
            h["Authorization"] = f"Bearer {self.cfg.api_key}"
        return h

    async def _attempt_register(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> tuple[bool, str]:
        base = self._active_base_url()
        headers = self._headers()

        ok, status, err = await _post_register(client, base, self._current_path, payload, headers)
        if ok:
            return True, ""
        # 404 → Endpoint existiert in dieser Router-Version nicht. Auf
        # Legacy-CRUD-Pfad zurueckfallen (PUT/POST nach Name-Match).
        if status == 404 and self._current_path == PRIMARY_PATH:
            log.info("Router %s: /register fehlt → Wechsel auf %s (legacy)", base, LEGACY_PATH)
            self._current_path = LEGACY_PATH
            ok2, status2, err2 = await _post_register(client, base, LEGACY_PATH, payload, headers)
            if ok2:
                return True, ""
            return False, f"legacy HTTP {status2}: {err2}"
        if status:
            return False, f"HTTP {status}: {err}"
        return False, err

    async def tick(self) -> None:
        snapshot: DiscoverySnapshot = await discover(self.cfg)
        self.state["last_snapshot"] = snapshot

        payload = _serialize(_payload_from_snapshot(self.cfg, snapshot))

        # Wir benutzen den HTTPX-Client mit follow_redirects, damit Caddy auch
        # einen 301/302 ohne Aufwand mitmachen kann.
        async with httpx.AsyncClient(follow_redirects=True) as client:
            ok, err = await self._attempt_register(client, payload)

        now = datetime.now(UTC)
        if ok:
            re_registered = self._last_was_failure
            self.status.connected = True
            self.status.last_register_at = now
            self.status.last_error = None
            self.status.consecutive_failures = 0
            self._backoff_s = self.cfg.register_interval_s
            self._last_was_failure = False
            if re_registered:
                log.info(
                    "Spoke '%s' registriert bei %s (services=%d, capabilities=%s)",
                    self.cfg.spoke_name,
                    self._active_base_url(),
                    len([s for s in snapshot.services if s.status == "ok"]),
                    ",".join(snapshot.capabilities) or "—",
                )
        else:
            self.status.connected = False
            self.status.last_error = err
            self.status.consecutive_failures += 1
            self._last_was_failure = True
            # Backoff verdoppeln (Cap = max_backoff_s)
            self._backoff_s = min(self._backoff_s * 2, self.cfg.max_backoff_s)
            log.warning(
                "Register fehlgeschlagen (%d in Folge) gegen %s: %s",
                self.status.consecutive_failures,
                self._active_base_url(),
                err,
            )
            # Auf Fallback umschalten?
            if (
                not self.status.using_fallback
                and self.cfg.fallback_router_url
                and self.status.consecutive_failures >= self.cfg.fallback_after_failures
            ):
                log.warning(
                    "Wechsle auf Fallback-Router %s nach %d Fehlversuchen.",
                    self.cfg.fallback_router_url,
                    self.status.consecutive_failures,
                )
                self.status.using_fallback = True
                self.status.consecutive_failures = 0
                self._backoff_s = self.cfg.register_interval_s
            elif (
                self.status.using_fallback
                and self.status.consecutive_failures >= self.cfg.fallback_after_failures
            ):
                # Auch Fallback haut nicht hin → zurueck auf primary, neuer Versuch
                log.warning("Fallback auch unerreichbar — zurueck auf Primary fuer naechsten Tick.")
                self.status.using_fallback = False
                self.status.consecutive_failures = 0
                self._backoff_s = self.cfg.register_interval_s

    @property
    def next_interval_s(self) -> int:
        return self._backoff_s


async def registration_loop(
    cfg_provider,
    state: dict[str, Any],
    stop_event: asyncio.Event,
) -> None:
    """Daueraufgabe.

    ``cfg_provider`` ist ein Callable, das die aktuelle Config liefert
    (damit Runtime-Aenderungen aus der Admin-UI ohne Restart greifen).
    """
    cfg = cfg_provider()
    registrar = Registrar(cfg, state)
    state["registrar"] = registrar

    while not stop_event.is_set():
        # Frische Config holen (Tags, URL, Key koennen geaendert sein)
        new_cfg = cfg_provider()
        if (
            new_cfg.router_url != registrar.cfg.router_url
            or new_cfg.fallback_router_url != registrar.cfg.fallback_router_url
            or new_cfg.api_key != registrar.cfg.api_key
            or new_cfg.registration_token != registrar.cfg.registration_token
            or new_cfg.spoke_tags != registrar.cfg.spoke_tags
        ):
            log.info("Config geaendert — Registrar wird neu initialisiert.")
            registrar.update_config(new_cfg)
        else:
            registrar.cfg = new_cfg

        try:
            await registrar.tick()
        except Exception as exc:  # noqa: BLE001
            log.exception("registration_loop tick error: %s", exc)
            registrar.status.connected = False
            registrar.status.last_error = str(exc)[:200]

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=registrar.next_interval_s)
        except TimeoutError:
            continue
        # stop_event gesetzt → Schleife verlassen
        return


def _service_capabilities(services: list[ServiceInfo]) -> list[str]:
    out: set[str] = set()
    for s in services:
        if s.status == "ok":
            out.update(s.capabilities)
    return sorted(out)
