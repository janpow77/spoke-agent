"""Konfigurations-Layer.

Konfig kommt ausschliesslich aus ENV-Variablen. Die einzige zustandsbehaftete
Information die wir persistieren (Router-URL, API-Key, Tags) liegt entweder
im OS-Keychain (``keyring``-Backend) oder — falls keine Keychain verfuegbar
ist — in der .env-Datei unter ``$SPOKE_AGENT_STATE_DIR``.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


# ----------------------------- Standard-Services --------------------------
# Welche Services entdeckt der Agent? Port + erwartete Capabilities. Wer eigene
# Services laufen hat, kann sie via ENV `SPOKE_EXTRA_SERVICES` (JSON-Array)
# ergaenzen — Default deckt unsere drei eigenen Workloads ab.

DEFAULT_SERVICES: list[dict] = [
    {
        "name": "ollama",
        "url": "http://127.0.0.1:11434",
        "health_path": "/api/tags",
        "type": "ollama",
        "capabilities": ["llm", "embedding"],
        "compose_service": "ollama",
    },
    {
        "name": "reranker-service",
        "url": "http://127.0.0.1:8004",
        "health_path": "/health",
        "type": "custom",
        "capabilities": ["rerank"],
        "compose_service": "reranker-service",
    },
    {
        "name": "vision-service",
        "url": "http://127.0.0.1:8005",
        "health_path": "/health",
        "type": "custom",
        "capabilities": ["vision", "ocr"],
        "compose_service": "vision-service",
    },
]


@dataclass
class SpokeAgentConfig:
    # --- Identitaet ---
    spoke_name: str = "spoke-host"
    spoke_tags: list[str] = field(default_factory=list)
    app_id: str = ""  # Optional — Router referenziert intern app_id

    # --- Router-Anbindung ---
    router_url: str = "http://100.99.159.80:8080"
    fallback_router_url: str | None = None
    api_key: str = ""
    registration_token: str = ""

    # --- Lokale Discovery ---
    docker_compose_path: str = "/etc/spoke-stack/compose.yaml"
    state_dir: str = "/data"
    state_file: str = "/data/state.json"

    # --- Listen ---
    bind_host: str = "0.0.0.0"
    bind_port: int = 7844

    # --- Auth (optional Bearer) ---
    admin_password: str = ""
    admin_password_is_default: bool = True

    # --- Verhalten ---
    register_interval_s: int = 30
    discovery_interval_s: int = 15
    max_backoff_s: int = 60
    fallback_after_failures: int = 3

    # --- Service-Definitionen ---
    services: list[dict] = field(default_factory=lambda: list(DEFAULT_SERVICES))


def _split_csv(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()]


def load_config() -> SpokeAgentConfig:
    """Sammelt Konfiguration aus ENV.

    Auf MacBook / NUC / evo-x2 / Desktop laeuft alles via Compose und ENV-File,
    deshalb gibt es keine YAML-Datei. Persistente Aenderungen am Router-URL/
    API-Key macht die Admin-UI ueber den ``config_store``.
    """
    cfg = SpokeAgentConfig()

    cfg.spoke_name = os.environ.get("SPOKE_NAME") or os.environ.get("HOSTNAME") or cfg.spoke_name
    cfg.spoke_tags = _split_csv(os.environ.get("SPOKE_TAGS", ""))
    cfg.app_id = os.environ.get("APP_ID", "")

    cfg.router_url = (os.environ.get("ROUTER_URL", cfg.router_url) or cfg.router_url).rstrip("/")
    fallback = os.environ.get("FALLBACK_ROUTER_URL")
    cfg.fallback_router_url = fallback.rstrip("/") if fallback else None

    cfg.api_key = os.environ.get("API_KEY", "")
    cfg.registration_token = os.environ.get("SPOKE_REGISTRATION_TOKEN", "")

    cfg.docker_compose_path = os.environ.get("DOCKER_COMPOSE_PATH", cfg.docker_compose_path)
    cfg.state_dir = os.environ.get("SPOKE_AGENT_STATE_DIR", cfg.state_dir)
    cfg.state_file = str(Path(cfg.state_dir) / "state.json")

    cfg.bind_host = os.environ.get("SPOKE_AGENT_BIND", cfg.bind_host)
    cfg.bind_port = int(os.environ.get("SPOKE_AGENT_PORT", str(cfg.bind_port)))

    admin_pw = os.environ.get("SPOKE_AGENT_ADMIN_PASSWORD")
    if admin_pw:
        cfg.admin_password = admin_pw
        cfg.admin_password_is_default = False
    else:
        cfg.admin_password = "spoke-admin"
        cfg.admin_password_is_default = True
        log.warning("SPOKE_AGENT_ADMIN_PASSWORD nicht gesetzt — Default 'spoke-admin' (NUR FUER LOKALE TESTS!)")

    cfg.register_interval_s = int(os.environ.get("SPOKE_REGISTER_INTERVAL_S", str(cfg.register_interval_s)))
    cfg.discovery_interval_s = int(os.environ.get("SPOKE_DISCOVERY_INTERVAL_S", str(cfg.discovery_interval_s)))
    cfg.max_backoff_s = int(os.environ.get("SPOKE_MAX_BACKOFF_S", str(cfg.max_backoff_s)))

    return cfg
