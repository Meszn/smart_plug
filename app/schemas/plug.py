"""
Priz request/response şemaları.
"""
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlugType(str, Enum):
    BASIC = "basic"
    ENERGY_MONITOR = "energy_monitor"
    SURGE_PROTECTOR = "surge_protector"


class ActionType(str, Enum):
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    RESTART = "restart"


# ── İstek şemaları ───────────────────────────────────────

class PlugCreate(BaseModel):
    """POST /plugs — ip_address zorunlu."""
    plug_type: PlugType
    name: Annotated[str, Field(min_length=1, max_length=100)]
    ip_address: Annotated[str, Field(
        description="Prizin IP adresi. Test için 'mock_basic' gibi değer verilebilir."
    )]
    location: str | None = None
    mac_address: str | None = None
    firmware_version: str | None = None
    notes: str | None = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re
        if not re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", v):
            raise ValueError("MAC adresi AA:BB:CC:DD:EE:FF formatında olmalıdır")
        return v.upper()


class PlugUpdate(BaseModel):
    """PUT /plugs/{id} — tüm alanlar opsiyonel."""
    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    ip_address: str | None = None
    location: str | None = None
    firmware_version: str | None = None
    notes: str | None = None


# ── Yanıt şemaları ───────────────────────────────────────

class PlugResponse(BaseModel):
    """Priz listesi — sadece kayıt bilgileri, dinamik durum yok."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    plug_type: str
    name: str
    location: str | None
    ip_address: str
    mac_address: str | None
    firmware_version: str | None
    created_at: datetime
    updated_at: datetime


class PlugDetail(PlugResponse):
    notes: str | None


# ── Model-spesifik durum şemaları ────────────────────────
# Cihazdan gelen anlık veriyi temsil eder.

class BasicPlugStatus(BaseModel):
    plug_id: int
    plug_type: Literal["basic"]
    name: str
    ip_address: str
    is_on: bool
    is_online: bool
    uptime_seconds: int | None = None


class EnergyMonitorPlugStatus(BaseModel):
    plug_id: int
    plug_type: Literal["energy_monitor"]
    name: str
    ip_address: str
    is_on: bool
    is_online: bool
    current_watt: float | None = Field(None, description="Anlık güç (W)")
    voltage: float | None = Field(None, description="Gerilim (V)")
    current_ampere: float | None = Field(None, description="Akım (A)")
    total_kwh: float | None = Field(None, description="Toplam tüketim (kWh)")
    power_factor: float | None = Field(None, description="Güç faktörü")


class SurgeProtectorPlugStatus(BaseModel):
    plug_id: int
    plug_type: Literal["surge_protector"]
    name: str
    ip_address: str
    is_on: bool
    is_online: bool
    protection_active: bool | None = None
    surge_count: int | None = None
    max_voltage_recorded: float | None = None
    protection_joules: int | None = None


# ── Diğer şemalar ─────────────────────────────────────────

class ActionResponse(BaseModel):
    success: bool
    action: ActionType
    plug_id: int
    plug_name: str
    message: str
    device_response: dict[str, Any] | None = None


class PaginatedPlugResponse(BaseModel):
    items: list[PlugResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str