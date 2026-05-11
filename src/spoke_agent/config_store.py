"""Persistente Konfig fuer Runtime-Aenderungen (Router-URL, API-Key, Tags).

Versucht Werte im OS-Keychain (``keyring``) zu speichern; faellt auf eine
JSON-Datei in ``state_dir`` zurueck, falls keine Keychain verfuegbar ist
(headless Linux-Container).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

log = logging.getLogger(__name__)

_KEYRING_SERVICE = "spoke-agent"
_LOCK = Lock()

# Schluessel, die wir zur Laufzeit ueberschreiben koennen.
RUNTIME_KEYS = ("router_url", "fallback_router_url", "api_key", "registration_token", "spoke_tags")


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        import keyring as _kr
        from keyring.backends.fail import Keyring as FailBackend

        backend = _kr.get_keyring()
        if isinstance(backend, FailBackend):
            return False
        return True
    except Exception:
        return False


def _file_path(state_dir: str) -> Path:
    return Path(state_dir) / "config-overrides.json"


def _read_file(state_dir: str) -> dict[str, Any]:
    p = _file_path(state_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        log.warning("Override-Datei nicht lesbar (%s): %s", p, exc)
        return {}


def _write_file(state_dir: str, data: dict[str, Any]) -> None:
    p = _file_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass


def load_overrides(state_dir: str) -> dict[str, Any]:
    """Liest alle gespeicherten Werte. Keychain hat Vorrang vor Datei."""
    with _LOCK:
        if _keyring_available():
            import keyring

            out: dict[str, Any] = {}
            for key in RUNTIME_KEYS:
                try:
                    v = keyring.get_password(_KEYRING_SERVICE, key)
                except Exception:  # noqa: BLE001
                    v = None
                if v is not None:
                    out[key] = v if key != "spoke_tags" else [s for s in v.split(",") if s]
            if out:
                return out
        return _read_file(state_dir)


def set_override(state_dir: str, key: str, value: Any) -> None:
    if key not in RUNTIME_KEYS:
        raise KeyError(f"Unsupported config key: {key}")
    with _LOCK:
        serialized = ",".join(value) if isinstance(value, list) else (value or "")
        if _keyring_available():
            try:
                import keyring

                keyring.set_password(_KEYRING_SERVICE, key, serialized or "")
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("Keychain-Set fehlgeschlagen, fallback Datei: %s", exc)
        data = _read_file(state_dir)
        data[key] = value
        _write_file(state_dir, data)


def apply_overrides(cfg, overrides: dict[str, Any]) -> None:
    """Wendet gespeicherte Overrides auf eine ``SpokeAgentConfig`` an."""
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            continue
        if k == "spoke_tags" and isinstance(v, str):
            v = [s.strip() for s in v.split(",") if s.strip()]
        setattr(cfg, k, v)
