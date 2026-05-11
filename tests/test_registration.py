"""Registrar-Backoff-Verhalten.

Wir mocken ``httpx.AsyncClient.post`` so dass er immer einen
ConnectionRefused wirft. Dann pruefen wir, dass der Backoff sich
verdoppelt und auf ``max_backoff_s`` capped.
"""
from __future__ import annotations

import pytest

from spoke_agent.config import SpokeAgentConfig
from spoke_agent.discovery import DiscoverySnapshot
from spoke_agent.models import HostInfo
from spoke_agent.registration import Registrar


@pytest.mark.asyncio
async def test_backoff_doubles(monkeypatch):
    cfg = SpokeAgentConfig()
    cfg.router_url = "http://127.0.0.1:9999"
    cfg.register_interval_s = 5
    cfg.max_backoff_s = 60
    cfg.fallback_after_failures = 99  # nicht durch Fallback-Switch verfaelschen lassen

    state: dict = {}
    reg = Registrar(cfg, state)

    async def fake_discover(_):
        return DiscoverySnapshot(host_info=HostInfo(hostname="ut"), services=[])

    monkeypatch.setattr("spoke_agent.registration.discover", fake_discover)

    # Erster Tick → backoff 10
    await reg.tick()
    assert reg.status.connected is False
    assert reg.next_interval_s == 10

    # Zweiter Tick → backoff 20
    await reg.tick()
    assert reg.next_interval_s == 20

    # Tick spaeter cappen → max 60
    for _ in range(10):
        await reg.tick()
    assert reg.next_interval_s == 60
    assert reg.status.consecutive_failures >= 5


@pytest.mark.asyncio
async def test_fallback_switch(monkeypatch):
    cfg = SpokeAgentConfig()
    cfg.router_url = "http://primary.invalid:9999"
    cfg.fallback_router_url = "http://fallback.invalid:9999"
    cfg.register_interval_s = 1
    cfg.max_backoff_s = 4
    cfg.fallback_after_failures = 3

    reg = Registrar(cfg, {})

    async def fake_discover(_):
        return DiscoverySnapshot(host_info=HostInfo(hostname="ut"), services=[])

    monkeypatch.setattr("spoke_agent.registration.discover", fake_discover)

    for _ in range(3):
        await reg.tick()
    assert reg.status.using_fallback is True
