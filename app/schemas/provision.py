"""
Provision şemaları — priz ilk kurulum request/response.
"""
from pydantic import BaseModel, Field


class ScanPlugAPRequest(BaseModel):
    """Çevredeki fabrika modundaki prizleri listele."""
    pass


class ProvisionRequest(BaseModel):
    """Prizi WiFi'a bağlama isteği."""
    plug_ap_ssid: str = Field(
        description="Prizin yayınladığı AP adı (örn: 'TP-Link_ECA5')",
        examples=["TP-Link_ECA5"],
    )
    target_ssid: str = Field(
        description="Prizin bağlanacağı WiFi ağı",
        examples=["OfisWiFi"],
    )
    target_password: str = Field(
        description="Hedef WiFi şifresi",
        examples=["sifre123"],
    )
    original_ssid: str | None = Field(
        default=None,
        description="İşlem sonrası dönülecek ağ. Boş bırakılırsa otomatik tespit edilir.",
    )


class ProvisionStep(BaseModel):
    step: str
    value: str


class ProvisionResponse(BaseModel):
    success: bool
    plug_ip: str | None
    model: str | None
    message: str
    steps: list[ProvisionStep]