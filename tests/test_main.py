"""HTTP-Smoketests fuer die Admin-API.

Auth ist via ``SPOKE_AGENT_AUTH=off`` ausgeschaltet, damit die Tests ohne
Login-Flow laufen koennen.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["SPOKE_AGENT_AUTH"] = "off"
    os.environ["SPOKE_AGENT_STATE_DIR"] = str(tmp_path_factory.mktemp("state"))
    os.environ["SPOKE_AGENT_ADMIN_PASSWORD"] = "test"
    os.environ["ROUTER_URL"] = "http://127.0.0.1:9999"
    # Reload-Trick: das Main-Modul beim 1. Import als app aufnehmen.
    from spoke_agent.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_status(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert "discovery" in body
    assert "router" in body


def test_services_list(client):
    r = client.get("/api/services")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_router_get(client):
    r = client.get("/api/router")
    assert r.status_code == 200
    body = r.json()
    assert body["url"]
