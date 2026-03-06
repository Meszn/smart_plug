"""
HS110 Adapter — Kasa serisi enerji izleme priz.

Protokol: KasaProtocol (XOR TCP port 9999)
Tip: energy_monitor
"""
from typing import Any

from app.adapters.base import BasePlugAdapter
from app.adapters.registry import PlugAdapterRegistry
from app.core.protocols.kasa_protocol import KasaProtocol
from app.core.polling import get_mock_response


class HS110Adapter(BasePlugAdapter):

    def _create_protocol(self) -> KasaProtocol:
        from app.core.config import get_settings
        settings = get_settings()
        return KasaProtocol(self.plug.ip_address, timeout=settings.polling_timeout)

    async def get_status(self) -> dict[str, Any]:
        if self._is_mock():
            raw = get_mock_response("energy_monitor")
            return {**self._base_meta(), **raw}

        proto = self.get_protocol()
        sysinfo = await proto.get_sysinfo()
        emeter = await proto.get_emeter()

        return {
            **self._base_meta(),
            "is_on": bool(sysinfo.get("relay_state", 0)),
            "is_online": True,
            # Enerji verileri — mV/mA/mW → V/A/W dönüşümü protokolde yapıldı
            "current_watt": emeter.get("power_w"),
            "voltage": emeter.get("voltage_v"),
            "current_ampere": emeter.get("current_a"),
            "total_kwh": emeter.get("total_kwh"),
            "power_factor": None,  # HS110 desteklemiyor
            # Ek Kasa bilgileri
            "alias": sysinfo.get("alias"),
            "rssi": sysinfo.get("rssi"),
            "on_time_seconds": sysinfo.get("on_time"),
        }

    async def get_device_info(self) -> dict[str, Any]:
        if self._is_mock():
            return {
                "model": "HS110(EU)",
                "mac": None,
                "firmware": "1.5.6",
                "plug_type": "energy_monitor",
                "protocol": "kasa",
            }
        proto = self.get_protocol()
        return await proto.get_device_info()


# Otomatik kayıt
PlugAdapterRegistry.register("hs110", HS110Adapter)