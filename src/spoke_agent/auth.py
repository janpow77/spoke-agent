"""Sehr leichte Bearer-Token-Auth fuer die Admin-UI.

Wir wollen *keine* Sessions in DB persistieren — das wuerde den Agent
sticky machen. Stattdessen: ein in-memory Set von gueltigen Tokens, mit
Ablauf. Token-Generierung passiert nach erfolgreichem Login mit dem
``SPOKE_AGENT_ADMIN_PASSWORD``.

Wenn die UI fuer einen Host explizit ohne Login laufen soll (Default
``spoke-admin`` zaehlt als Default-Passwort und faellt unter Tailscale-only
Bind als ``trusted_local`` durch), kann ``require_auth`` per ENV
``SPOKE_AGENT_AUTH=off`` komplett ausgeschaltet werden.
"""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

SESSION_TTL_S = 12 * 60 * 60  # 12h


@dataclass
class Session:
    token: str
    expires_at_epoch: float


_SESSIONS: dict[str, Session] = {}


def _auth_disabled() -> bool:
    return (os.environ.get("SPOKE_AGENT_AUTH", "on").lower() in ("off", "false", "0"))


def issue_token() -> Session:
    token = secrets.token_urlsafe(32)
    s = Session(token=token, expires_at_epoch=time.time() + SESSION_TTL_S)
    _SESSIONS[token] = s
    return s


def revoke_token(token: str) -> None:
    _SESSIONS.pop(token, None)


def _purge() -> None:
    now = time.time()
    for k, s in list(_SESSIONS.items()):
        if s.expires_at_epoch < now:
            _SESSIONS.pop(k, None)


def require_auth(request: Request) -> Session | None:
    if _auth_disabled():
        return None
    _purge()
    h = request.headers.get("authorization") or request.headers.get("Authorization")
    if not h:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization")
    if not h.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = h.split(" ", 1)[1].strip()
    s = _SESSIONS.get(token)
    if not s or s.expires_at_epoch < time.time():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return s
