# spoke-agent

Pro-Host-Agent fuer das LLM-Router-Tailnet (NUC, evo-x2, Desktop, MacBook).

Aufgaben:
- Entdeckt lokal laufende ML-Services (ollama, reranker-service, vision-service)
  ueber HTTP-Probes auf den Standard-Ports (11434, 8004, 8005).
- Detect-GPU: nvidia-smi (Linux) bzw. system_profiler (macOS).
- Registriert den Host als Spoke beim zentralen `llm-router`
  (`POST <router>/admin/api/spokes/register`) und schickt alle 30 s einen
  Heartbeat mit aktualisiertem Status.
- Bietet eine lokale Admin-UI unter `/admin/` mit fuenf Views:
  Dashboard, Services, Update, Config, Logs.
- Erlaubt `docker compose restart/stop/start` und `docker compose pull/up -d`
  via UI — alles ueber den gemounteten `/var/run/docker.sock`.

## Architektur

```
+--------------------------+        +-----------------------+
| spoke-agent (this repo)  |  ----> | llm-router (CCX23)    |
|  - discovery loop        |        |  - /spokes/register   |
|  - register loop (30 s)  |        |  - heartbeat tracking |
|  - admin UI :7844        |        +-----------------------+
|  - docker compose ops    |
+--------------------------+
       |          |          |
       v          v          v
   ollama   reranker    vision
   :11434   :8004       :8005
```

## Quick Start (Dev)

```bash
# Backend
pip install -e .[dev]
uvicorn spoke_agent.main:app --reload --port 7844

# Frontend
cd frontend
npm install
npm run dev   # → http://localhost:5182, proxied an :7844
```

## Deploy

Container ist single-binary: `docker run -d -v /var/run/docker.sock:/var/run/docker.sock:ro ...`.
Volle Compose-Konfig + Hilfs-Services liegen im **separaten Repo
[`spoke-stack`](https://github.com/janpow77/spoke-stack)**.

## ENV-Konfig

Siehe `.env.example`. Wichtige Variablen:

| Variable | Default | Zweck |
|---|---|---|
| `SPOKE_NAME` | hostname | Identitaet im Router |
| `ROUTER_URL` | `http://100.99.159.80:8080` | Primary Router |
| `FALLBACK_ROUTER_URL` | — | Wird benutzt nach 3x Failure auf primary |
| `API_KEY` | — | Bearer-Token fuer Router-Calls |
| `SPOKE_REGISTRATION_TOKEN` | — | `X-Spoke-Token` Header beim register |
| `DOCKER_COMPOSE_PATH` | `/etc/spoke-stack/compose.yaml` | Pfad zum Spoke-Stack-Compose |
| `SPOKE_AGENT_ADMIN_PASSWORD` | `spoke-admin` | Login-Passwort der UI |
| `SPOKE_AGENT_AUTH` | `on` | `off` schaltet die UI-Auth ab (nur Tailscale!) |

## API

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/health` | Liveness-Check (kein Auth) |
| POST | `/api/auth/login` | Login (`{"password": "..."}`) |
| GET | `/api/status` | Agent + Discovery + Router-Status |
| GET | `/api/services` | Liste aller entdeckten Services |
| POST | `/api/services/{name}/restart` | `docker compose restart` |
| POST | `/api/services/{name}/stop` | `docker compose stop` |
| POST | `/api/services/{name}/start` | `docker compose start` |
| GET | `/api/services/{name}/logs?tail=200` | `docker logs --tail N` |
| GET/PUT | `/api/services/{name}/config` | Service-ENV (whitelist pro Typ) |
| GET/PUT | `/api/router` | Router-URL, API-Key, Tags |
| POST | `/api/update` | `docker compose pull + up -d` |
| WS | `/api/logs/stream` | Live-Logs aller Services |

## Tests

```bash
pip install -e .[dev]
pytest -q
```

CI fuehrt zusaetzlich `ruff check` aus.
