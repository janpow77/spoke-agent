# spoke-agent

Pro-Host-Agent für das LLM-Router-Tailnet (NUC, evo-x2, Desktop, MacBook). Entdeckt lokal laufende ML-Services (ollama, reranker-service, vision-service) per HTTP-Probe, registriert den Host als Spoke beim zentralen `llm-router` (mit 30-s-Heartbeat) und bietet eine Admin-UI für `docker compose`-Operationen über den gemounteten Docker-Socket.

## Tech-Stack

- **Backend:** Python ≥3.12, FastAPI + Uvicorn (ASGI), Pydantic v2 / pydantic-settings, httpx, websockets, PyYAML, keyring (optionaler OS-Keychain, Fallback `.env`).
- **Frontend:** Vue 3 + Vue Router + Pinia, TypeScript, Vite 6, Tailwind CSS 4, axios, lucide-vue-next. Wird als SPA gebaut und vom Backend unter `/admin/` ausgeliefert.
- **Service-Discovery (Default-Ports):** ollama `:11434`, reranker-service `:8004`, vision-service `:8005`.
- **Agent-Port:** `:7844` (Backend + Admin-UI). Frontend-Dev-Server: `:5182` (Proxy `/api` + `/health` → `:7844`).
- **Container:** Multi-Stage Dockerfile (node:20-alpine Frontend-Build → python:3.12-slim Runtime mit `docker-ce-cli` + `docker-compose-plugin`, tini als Entrypoint). Image: `ghcr.io/janpow77/spoke-agent`.
- **Externe Abhängigkeiten:** zentraler `llm-router` (Default `http://100.99.159.80:8080`); Docker-Operationen über gemounteten `/var/run/docker.sock`. Volle Compose-Konfig liegt im separaten Repo `spoke-stack`.

## Setup & Befehle

```bash
# Backend installieren (inkl. Dev-Tools) + Dev-Server
pip install -e .[dev]
uvicorn spoke_agent.main:app --reload --port 7844

# Tests
pytest -q

# Lint (so wie in CI)
ruff check src tests

# Frontend
cd frontend
npm install
npm run dev            # Dev-Server auf :5182, Proxy an :7844
npm run build          # vue-tsc --noEmit + vite build
npm run build:nocheck  # vite build ohne Type-Check (im Dockerfile genutzt)
npm run type-check     # vue-tsc --noEmit

# Container bauen / starten
docker build -t spoke-agent .
docker run -d -v /var/run/docker.sock:/var/run/docker.sock:ro -p 7844:7844 spoke-agent
```

Konfiguration ausschließlich über ENV (siehe `.env.example`); keine YAML-Konfig. Persistente Änderungen (Router-URL, API-Key, Tags) macht die Admin-UI über den `config_store` (`$SPOKE_AGENT_STATE_DIR`, Default `/data`). Wichtige Variablen: `SPOKE_NAME`, `ROUTER_URL`, `FALLBACK_ROUTER_URL`, `API_KEY`, `SPOKE_REGISTRATION_TOKEN`, `DOCKER_COMPOSE_PATH`, `SPOKE_AGENT_ADMIN_PASSWORD`, `SPOKE_AGENT_AUTH` (`off` schaltet UI-Auth ab — nur in Tailscale-only-Setups).

## Struktur

```
src/spoke_agent/      Backend-Paket
  main.py             FastAPI-App: Lifespan, alle /api/*-Routen, WS /api/logs/stream, SPA-Mount /admin/
  models.py           Pydantic-Schemas (ServiceInfo, DiscoverySnapshot, RouterStatus, AgentStatus, Login*, ...)
  config.py           SpokeAgentConfig + load_config() (ENV-Layer, DEFAULT_SERVICES)
  config_store.py     Persistente Overrides (Keychain / .env im state_dir)
  discovery.py        Service-Discovery (HTTP-Probes, GPU-Detect, SERVICE_EDITABLE_ENV)
  docker_ops.py       docker compose restart/stop/start/pull-up, docker logs (+ Live-Stream)
  registration.py     Register-/Heartbeat-Loop zum llm-router (Fallback nach Failures)
  auth.py             Bearer-Token-Sessions (issue/revoke/require_auth, Auth-Disable-Schalter)
frontend/             Vue-3-SPA (src/App.vue, src/main.ts; Views: Dashboard, Services, Update, Config, Logs)
tests/                pytest (test_main.py, test_discovery.py, test_registration.py)
graphify-out/         Generierter Abhängigkeitsgraph (graph.json/graph.html)
Dockerfile, .github/workflows/image.yml   Build + CI/CD (GHCR)
```

Zentrale Module laut Abhängigkeitsgraph (`graphify-out/graph.json`): `main.py` (höchste Zentralität), `models.py`, `config.py`, `docker_ops.py`, `discovery.py`, `registration.py`.

## Konventionen

- **Lint/Format:** Ruff (`line-length = 110`, `target-version = py312`, Regeln `E,F,I,B,UP,N`; ignoriert `E501`, `B008`). CI führt `ruff check src tests` aus.
- **Tests:** pytest mit `asyncio_mode = auto`, `pythonpath = ["src"]`, `testpaths = ["tests"]`.
- **CI:** `.github/workflows/image.yml` läuft auf push/PR (`master`/`main`) — erst `ruff check` + `pytest -q`, dann Docker-Build & Push nach GHCR.
- **Sprache:** Code-Doku und UI-Texte auf Deutsch mit echten Umlauten (ä/ö/ü/ß).
