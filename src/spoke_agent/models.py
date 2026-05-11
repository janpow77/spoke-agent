"""Pydantic-Schemas (Wire-Format).

Schemas hier sind voellig zustandslos — der Agent persistiert nichts in einer
DB, ausser ``config_store``-Overrides. Discovery-Snapshots leben im
Application-State.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---- Discovery + Services ------------------------------------------------


class GpuInfo(BaseModel):
    device: str | None = None
    vram_total_mb: int | None = None
    vram_used_mb: int | None = None
    util_pct: float | None = None


class HostInfo(BaseModel):
    hostname: str = ""
    platform: str = ""
    arch: str = ""
    kernel: str | None = None
    container_runtime: str | None = None


class ServiceInfo(BaseModel):
    """Ergebnis-Snapshot eines entdeckten Service."""

    name: str
    type: str = "custom"
    base_url: str
    capabilities: list[str] = Field(default_factory=list)
    status: str = "unknown"  # ok | down | unreachable | unknown
    version: str | None = None
    image_digest: str | None = None
    container_id: str | None = None
    container_state: str | None = None
    last_check_at: datetime | None = None
    last_error: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    compose_service: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DiscoverySnapshot(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    gpu: GpuInfo | None = None
    host_info: HostInfo = Field(default_factory=HostInfo)
    services: list[ServiceInfo] = Field(default_factory=list)
    refreshed_at: datetime | None = None


# ---- Router-Anbindung (was wir POSTen) -----------------------------------


class RouterStatus(BaseModel):
    url: str
    fallback_url: str | None = None
    using_fallback: bool = False
    connected: bool = False
    last_register_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    app_id: str = ""


class SpokeRegisterPayload(BaseModel):
    """Wire-Format an POST <router>/admin/api/spokes/register.

    Spiegelt das ``SpokeCreate``-Schema im llm-router (plus die neuen Felder
    ``source`` und ``fallback_url``, die ein paralleler Agent ergaenzt).
    """

    name: str
    base_url: str
    type: str = "custom"
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    priority: int = 100
    gpu_info: GpuInfo | None = None
    services: list[ServiceInfo] = Field(default_factory=list)
    host_info: HostInfo = Field(default_factory=HostInfo)
    # Neue Felder (vom llm-router-Agent parallel ergaenzt):
    source: str = "dynamic"
    fallback_url: str | None = None
    enabled: bool = True


# ---- API-Antworten -------------------------------------------------------


class AgentStatus(BaseModel):
    spoke_name: str
    spoke_tags: list[str] = Field(default_factory=list)
    version: str
    uptime_s: int
    discovery: DiscoverySnapshot
    router: RouterStatus


class ServiceLogResponse(BaseModel):
    service: str
    lines: list[str]
    tail: int


class ServiceConfigResponse(BaseModel):
    service: str
    env: dict[str, str] = Field(default_factory=dict)
    editable_keys: list[str] = Field(default_factory=list)


class ServiceConfigUpdate(BaseModel):
    env: dict[str, str]


class RouterConfig(BaseModel):
    url: str | None = None
    fallback_url: str | None = None
    api_key: str | None = None
    registration_token: str | None = None
    spoke_tags: list[str] | None = None


class UpdateRequest(BaseModel):
    service: str = "all"


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime


class MeResponse(BaseModel):
    logged_in: bool
    expires_at: datetime | None = None
