# Architektur — spoke-agent

_Automatisch generiert von graphify-kira aus dem Code-Graphen. Nicht von Hand editieren — wird beim nächsten Lauf überschrieben._

**Umfang:** 311 Knoten, 845 Kanten, 12 größere Module, 0 zirkuläre Abhängigkeiten.

## Modulkarte

- **Auth & Config** (70): `auth.py`, `config.py`, `config_store.py`, `discovery.py`, `docker_ops.py`
- **Agent API** (46): `App.vue`, `agent.ts`, `client.ts`, `types.ts`, `main.ts`
- **FastAPI Framework** (37): `docker_ops.py`, `RuntimeError`, `main.py`, `models.py`, `BaseModel`
- **Hardware Discovery** (33): `config.py`, `discovery.py`, `models.py`, `test_discovery.py`
- **Agent Registration** (32): `__init__.py`, `models.py`, `registration.py`, `test_registration.py`
- **Frontend Setup** (25): `package.json`
- **TypeScript Config** (23): `tsconfig.json`
- **Data Formatting** (7): `format.ts`
- **Admin API Tests** (7): `test_main.py`
- **Env Variables** (3): `env.d.ts`
- **Polling Utility** (3): `poll.ts`
- **Toast Notifications** (3): `toast.ts`

## Zentrale Bausteine (God Nodes)

_Hohe Zentralität ist nicht automatisch ein Defekt (zentrale Stores/Modelle sind oft legitim). Konkrete Refactoring-Prioritäten siehe Optimierungs-Report._

- `BaseModel` — Grad 15 (ein 15/aus 0)
- `main.py (src/spoke_agent/main.py)` — Grad 67 (ein 1/aus 66)
- `ServiceInfo (src/spoke_agent/models.py)` — Grad 42 (ein 41/aus 1)
- `DiscoverySnapshot (src/spoke_agent/models.py)` — Grad 41 (ein 40/aus 1)
- `SpokeAgentConfig (src/spoke_agent/config.py)` — Grad 39 (ein 39/aus 0)
- `RouterStatus (src/spoke_agent/models.py)` — Grad 32 (ein 31/aus 1)
- `DockerError (src/spoke_agent/docker_ops.py)` — Grad 28 (ein 27/aus 1)
- `agent.ts (frontend/src/api/agent.ts)` — Grad 29 (ein 3/aus 26)
- `discovery.py (src/spoke_agent/discovery.py)` — Grad 23 (ein 5/aus 18)
- `get_config() (src/spoke_agent/main.py)` — Grad 18 (ein 14/aus 4)

## Schnittstellen / Brücken (Betweenness)

- `discover() (src/spoke_agent/discovery.py)` — Betweenness 0.003
- `get_config() (src/spoke_agent/main.py)` — Betweenness 0.002
- `discovery.py (src/spoke_agent/discovery.py)` — Betweenness 0.002
- `Registrar (src/spoke_agent/registration.py)` — Betweenness 0.002
- `.tick() (src/spoke_agent/registration.py)` — Betweenness 0.002
- `main.py (src/spoke_agent/main.py)` — Betweenness 0.001
- `agent.ts (frontend/src/api/agent.ts)` — Betweenness 0.001
- `registration.py (src/spoke_agent/registration.py)` — Betweenness 0.001
- `detect_gpu() (src/spoke_agent/discovery.py)` — Betweenness 0.001
- `registration_loop() (src/spoke_agent/registration.py)` — Betweenness 0.001

## Hinweis für Änderungen

Vor dem Ändern eines zentralen Bausteins die Abhängigen prüfen — am schnellsten über den **graphify-MCP** (globaler Graph): „Was hängt an `<datei>`?". Brücken-Knoten stabil halten.

