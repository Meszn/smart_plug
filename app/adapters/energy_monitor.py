"""
Enerji İzleme Priz Adapter'ı (energy_monitor).
Tapo P110/P115 gibi HTTP tabanlı cihazlar için.
Mock modda simüle edilmiş veri döner.
"""
from typing import Any

from app.adapters.base import BasePlugAdapter
from app.adapters.registry import PlugAdapterRegistry
from app.core.polling import get_mock_response
from app.core.protocols.kasa_protocol import KasaProtocol


class EnergyMonitorPlugAdapter(BasePlugAdapter):

    def _create_protocol(self) -> KasaProtocol:
        from app.core.config import get_settings
        return KasaProtocol(self.plug.ip_address, get_settings().polling_timeout)

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
            "current_watt": emeter.get("power_w"),
            "voltage": emeter.get("voltage_v"),
            "current_ampere": emeter.get("current_a"),
            "total_kwh": emeter.get("total_kwh"),
            "power_factor": None,
        }

    async def get_device_info(self) -> dict[str, Any]:
        if self._is_mock():
            return {
                "model": "P110",
                "mac": None,
                "firmware": "1.2.3",
                "plug_type": "energy_monitor",
                "protocol": "kasa",
            }
        proto = self.get_protocol()
        return await proto.get_device_info()


PlugAdapterRegistry.register("energy_monitor", EnergyMonitorPlugAdapter)