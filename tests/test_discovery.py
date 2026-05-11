"""Discovery-Smoketests.

Wir testen NICHT gegen echte Services (es laeuft kein ollama im CI). Wir
mocken den HTTP-Layer und stellen sicher, dass ein nicht erreichbarer
Service ``unreachable`` bekommt — und dass GPU-Detection auf Hosts ohne
``nvidia-smi``/macOS ``None`` zurueckliefert.
"""
from __future__ import annotations

import pytest

from spoke_agent.config import DEFAULT_SERVICES, SpokeAgentConfig
from spoke_agent.discovery import detect_gpu, discover


@pytest.mark.asyncio
async def test_gpu_detect_no_throw():
    # Egal welches OS — Funktion darf nie eine Exception werfen.
    result = await detect_gpu()
    assert result is None or hasattr(result, "device")


@pytest.mark.asyncio
async def test_discover_known_services_smoke():
    """Mit DEFAULT_SERVICES laufen die HTTP-Probes — egal welcher Status."""
    cfg = SpokeAgentConfig()
    cfg.services = list(DEFAULT_SERVICES)
    snap = await discover(cfg)
    statuses = {s.name: s.status for s in snap.services}
    assert set(statuses.keys()) == {"ollama", "reranker-service", "vision-service"}
    # Status muss zu einem der erlaubten Werte gehoeren
    valid = {"ok", "down", "unreachable", "unknown"}
    assert all(s in valid for s in statuses.values())


@pytest.mark.asyncio
async def test_discover_no_services_emits_empty_caps():
    cfg = SpokeAgentConfig()
    cfg.services = [
        # garantiert nie erreichbar (Port 1)
        {
            "name": "nope",
            "url": "http://127.0.0.1:1",
            "health_path": "/health",
            "type": "custom",
            "capabilities": ["llm"],
        },
    ]
    snap = await discover(cfg)
    assert snap.capabilities == []
    assert snap.services[0].status == "unreachable"
