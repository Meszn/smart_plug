"""
Priz ORM modeli.

Veritabanında SADECE sabit kayıt bilgileri tutulur:
  - Adı, konumu, IP adresi, MAC adresi
  - Priz tipi (hangi adapter kullanılacak)
  - Firmware versiyonu

Dinamik veriler (watt, açık/kapalı) veritabanında SAKLANMAZ.
Her sorguda fiziksel cihazdan anlık çekilir.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Plug(Base):
    __tablename__ = "plugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Polimorfik discriminator — hangi adapter seçilecek
    plug_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Adapter tipi: basic | energy_monitor | surge_protector"
    )

    # Sabit kimlik bilgileri
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Polling için zorunlu — cihazın ağ adresi
    ip_address: Mapped[str] = mapped_column(
        String(45), nullable=False,
        comment="Cihazın IP adresi. 'mock' ile başlarsa simülasyon kullanılır."
    )

    mac_address: Mapped[str | None] = mapped_column(
        String(17), nullable=True, unique=True,
        comment="Cihazın MAC adresi — ağ taramada otomatik doldurulur"
    )
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_on": plug_type,
        "polymorphic_identity": "plug",
    }

    def __repr__(self) -> str:
        return (
            f"<Plug id={self.id} name='{self.name}' "
            f"type='{self.plug_type}' ip='{self.ip_address}'>"
        )


class BasicPlug(Plug):
    """Sadece açma/kapama özelliği olan temel akıllı priz."""
    __mapper_args__ = {"polymorphic_identity": "basic"}


class EnergyMonitorPlug(Plug):
    """Watt, voltaj, amper, kWh ölçen enerji izleme priz."""
    __mapper_args__ = {"polymorphic_identity": "energy_monitor"}


class SurgeProtectorPlug(Plug):
    """Aşırı gerilim koruması olan priz."""
    __mapper_args__ = {"polymorphic_identity": "surge_protector"}