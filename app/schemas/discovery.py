"""
Ağ keşif (discovery) şemaları.

Akış:
  1. Kullanıcı → POST /discovery/scan    → ağı tara
  2. API → bulunan Tapo cihazlarını listele
  3. Kullanıcı → POST /discovery/register → seçilen cihazı kaydet
"""
from typing import Any
from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """
    Ağ tarama isteği.

    subnet: "192.168.1" gibi ilk 3 oktet.
    API bu subnet'teki .1 - .254 arasını tarar.
    """
    subnet: str = Field(
        default="192.168.1",
        description="Taranacak subnet (örn: '192.168.1')",
        examples=["192.168.1", "10.0.0"],
    )
    timeout: float = Field(
        default=1.0,
        ge=0.3,
        le=5.0,
        description="Her IP için bekleme süresi (saniye)",
    )


class DiscoveredDevice(BaseModel):
    """
    Ağ taramasında bulunan tek bir Tapo cihazı.
    Henüz veritabanına kaydedilmemiş, sadece keşfedilmiş.
    """
    ip_address: str = Field(description="Cihazın IP adresi")
    mac_address: str | None = Field(None, description="Cihazın MAC adresi")
    model: str | None = Field(None, description="Cihaz modeli (örn: 'P110', 'P100')")
    plug_type: str = Field(description="Eşleşen adapter tipi (basic | energy_monitor | surge_protector)")
    firmware_version: str | None = Field(None, description="Firmware versiyonu")
    already_registered: bool = Field(
        default=False,
        description="Bu cihaz zaten veritabanında kayıtlı mı?"
    )
    raw_info: dict[str, Any] | None = Field(
        None,
        description="Cihazdan gelen ham JSON verisi"
    )


class ScanResult(BaseModel):
    """Tarama sonucu özeti."""
    subnet: str
    scanned_count: int = Field(description="Taranan IP sayısı")
    found_count: int = Field(description="Bulunan Tapo cihazı sayısı")
    devices: list[DiscoveredDevice]


class RegisterDeviceRequest(BaseModel):
    """
    Keşfedilen cihazı sisteme kaydetme isteği.
    Kullanıcı frontend'den hangi cihazı kaydetmek istediğini seçer
    ve isteğe bağlı olarak isim ve konum ekler.
    """
    ip_address: str = Field(description="Kaydedilecek cihazın IP adresi")
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Kullanıcı tanımlı isim (örn: 'Salon TV Prizi')",
    )
    location: str | None = Field(
        None,
        description="Fiziksel konum (örn: 'Oturma Odası - Sol Duvar')",
    )
    notes: str | None = None