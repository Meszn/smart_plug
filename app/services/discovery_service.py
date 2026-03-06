"""
Ağ Keşif Servisi — TCP 9999 ile Kasa/HS cihazlarını bulur.

Tarama Algoritması:
  1. Subnet'teki her IP'ye TCP:9999 bağlantı dene
  2. Bağlantı varsa get_sysinfo komutu gönder
  3. "IOT.SMARTPLUG" tipi yanıt → Kasa/HS cihazı
  4. Model → plug_type belirle → DiscoveredDevice oluştur
"""
import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.protocols.kasa_protocol import KasaProtocol
from app.models.plug import Plug
from app.schemas.discovery import DiscoveredDevice, ScanResult

logger = logging.getLogger(__name__)
settings = get_settings()

# Model → adapter tipi eşlemesi
# Yeni model gelince buraya ekle
MODEL_TO_ADAPTER: dict[str, str] = {
    # Kasa serisi — temel
    "HS100": "hs100",
    "HS103": "hs100",
    "HS105": "hs100",
    "HS200": "hs100",
    # Kasa serisi — enerji izleme
    "HS110": "hs110",
    "HS115": "hs110",
    # Tapo serisi — temel (ileride eklenecek)
    "P100": "basic",
    "P105": "basic",
    # Tapo serisi — enerji izleme
    "P110": "energy_monitor",
    "P115": "energy_monitor",
    # Tapo serisi — surge
    "P300": "surge_protector",
}


class DiscoveryService:

    def __init__(self, db: Session) -> None:
        self.db = db

    async def scan_network(
            self,
            subnet: str,
            timeout: float | None = None,
    ) -> ScanResult:
        scan_timeout = timeout or settings.network_scan_timeout

        # Birden fazla subnet destekle: "10.141.1,10.141.5" gibi
        subnets = [s.strip() for s in subnet.split(",")]
        all_ips = []
        for sn in subnets:
            all_ips.extend([f"{sn}.{i}" for i in range(1, 255)])

        logger.info(
            f"Ağ taraması başlıyor: {len(all_ips)} IP, "
            f"subnet(ler): {subnets} (timeout={scan_timeout}s)"
        )

        semaphore = asyncio.Semaphore(settings.network_scan_concurrency)
        tasks = [self._probe_ip(ip, scan_timeout, semaphore) for ip in all_ips]
        results = await asyncio.gather(*tasks)

        devices = [r for r in results if r is not None]

        registered_ips = self._get_registered_ips()
        for device in devices:
            device.already_registered = device.ip_address in registered_ips

        logger.info(
            f"Tarama tamamlandı: {len(all_ips)} IP tarandı, "
            f"{len(devices)} cihaz bulundu."
        )

        return ScanResult(
            subnet=subnet,
            scanned_count=len(all_ips),
            found_count=len(devices),
            devices=devices,
        )

    async def _probe_ip(
        self,
        ip: str,
        timeout: float,
        semaphore: asyncio.Semaphore,
    ) -> DiscoveredDevice | None:
        """
        Tek IP'ye Kasa protokolüyle bağlanmayı dener.
        get_sysinfo yanıtı IOT.SMARTPLUG içeriyorsa cihaz bulundu.
        """
        async with semaphore:
            try:
                proto = KasaProtocol(ip, timeout=timeout)
                sysinfo = await proto.get_sysinfo()

                # Kasa/HS cihazı mı?
                device_type = sysinfo.get("type", "")
                if "SMARTPLUG" not in device_type.upper():
                    return None

                return self._build_device(ip, sysinfo)

            except Exception:
                # Cihaz yok veya yanıt vermiyor — normal
                return None

    def _build_device(self, ip: str, sysinfo: dict[str, Any]) -> DiscoveredDevice:
        """sysinfo'dan DiscoveredDevice oluşturur."""
        raw_model = sysinfo.get("model", "UNKNOWN")
        # "HS110(EU)" → "HS110"
        model_clean = raw_model.split("(")[0].strip()
        adapter_type = MODEL_TO_ADAPTER.get(model_clean, "hs100")

        mac = sysinfo.get("mac", "").replace("-", ":")

        return DiscoveredDevice(
            ip_address=ip,
            mac_address=mac or None,
            model=raw_model,
            plug_type=adapter_type,
            firmware_version=sysinfo.get("sw_ver"),
            already_registered=False,
            raw_info=sysinfo,
        )

    def _get_registered_ips(self) -> set[str]:
        rows = self.db.execute(select(Plug.ip_address)).scalars().all()
        return set(rows)

    async def register_device(
        self,
        ip_address: str,
        name: str,
        location: str | None = None,
        notes: str | None = None,
    ) -> Plug:
        from fastapi import HTTPException, status

        # Zaten kayıtlı mı?
        existing = self.db.execute(
            select(Plug).where(Plug.ip_address == ip_address)
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{ip_address}' zaten kayıtlı (ID={existing.id})",
            )

        # Cihaz bilgisini çek
        try:
            proto = KasaProtocol(ip_address, timeout=5.0)
            info = await proto.get_device_info()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cihaza ulaşılamıyor [{ip_address}]: {e}",
            )

        plug = Plug(
            plug_type=info["plug_type"],
            name=name,
            ip_address=ip_address,
            mac_address=info.get("mac") or None,
            firmware_version=info.get("firmware"),
            location=location,
            notes=notes,
        )
        self.db.add(plug)
        self.db.flush()
        self.db.refresh(plug)

        logger.info(
            f"Cihaz kaydedildi: {name} ({info['model']}) "
            f"→ {ip_address} [tip: {info['plug_type']}]"
        )
        return plug
