"""
Tapo Protokolü — P100/P110 KLAP HTTP iletişimi.

Tapo yeni nesil cihazlar AES+RSA şifreli KLAP protokolü kullanır.
Bunu sıfırdan implement etmek yerine 'tapo' kütüphanesini kullanırız.

Kurulum: pip install tapo

Desteklenen modeller:
  P100, P105      → temel on/off
  P110, P115      → on/off + enerji izleme
  P300, P304M     → surge/çoklu priz
"""
from typing import Any

from app.core.protocols.base_protocol import BaseProtocol
from app.core.config import get_settings

settings = get_settings()

MODEL_TYPE_MAP: dict[str, str] = {
    "P100": "basic",
    "P105": "basic",
    "P125": "basic",
    "P110": "energy_monitor",
    "P115": "energy_monitor",
    "P125M": "energy_monitor",
    "P300": "surge_protector",
    "P304M": "surge_protector",
}


class TapoProtocol(BaseProtocol):

    async def _get_client(self):
        """
        tapo kütüphanesi client'ı oluşturur.
        Her çağrıda yeni client — state tutmuyoruz.
        """
        try:
            from tapo import ApiClient
        except ImportError:
            raise RuntimeError(
                "Tapo kütüphanesi yüklü değil. "
                "Çalıştır: pip install tapo"
            )

        if not settings.tapo_email or not settings.tapo_password:
            raise RuntimeError(
                "Tapo credentials eksik. "
                ".env dosyasına TAPO_EMAIL ve TAPO_PASSWORD ekle."
            )

        client = ApiClient(settings.tapo_email, settings.tapo_password)
        return client

    async def get_sysinfo(self) -> dict[str, Any]:
        client = await self._get_client()
        device = await client.p110(self.ip)
        info = await device.get_device_info()
        return info.to_dict()

    async def get_emeter(self) -> dict[str, Any]:
        try:
            client = await self._get_client()
            device = await client.p110(self.ip)
            usage = await device.get_current_power()
            return {
                "voltage_v": None,
                "current_a": None,
                "power_w": usage.current_power / 1000 if usage.current_power else 0,
                "total_kwh": None,
            }
        except Exception:
            return {}

    async def set_relay(self, state: bool) -> bool:
        try:
            client = await self._get_client()
            device = await client.p110(self.ip)
            if state:
                await device.on()
            else:
                await device.off()
            return True
        except Exception:
            return False

    async def get_device_info(self) -> dict[str, Any]:
        sysinfo = await self.get_sysinfo()
        raw_model = sysinfo.get("model", "")
        model_clean = raw_model.split("(")[0].strip()
        plug_type = MODEL_TYPE_MAP.get(model_clean, "basic")

        return {
            "model": raw_model,
            "model_clean": model_clean,
            "mac": sysinfo.get("mac", ""),
            "firmware": sysinfo.get("fw_ver", ""),
            "alias": sysinfo.get("nickname", ""),
            "plug_type": plug_type,
            "protocol": "tapo",
        }