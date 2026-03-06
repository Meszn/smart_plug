"""
Aşırı Gerilim Koruyucu Priz Adapter'ı (surge_protector).
"""
from typing import Any

from app.adapters.base import BasePlugAdapter
from app.adapters.registry import PlugAdapterRegistry
from app.core.polling import get_mock_response
from app.core.protocols.kasa_protocol import KasaProtocol


class SurgeProtectorPlugAdapter(BasePlugAdapter):

    def _create_protocol(self) -> KasaProtocol:
        from app.core.config import get_settings
        return KasaProtocol(self.plug.ip_address, get_settings().polling_timeout)

    async def get_status(self) -> dict[str, Any]:
        if self._is_mock():
            raw = get_mock_response("surge_protector")
            return {**self._base_meta(), **raw}

        proto = self.get_protocol()
        sysinfo = await proto.get_sysinfo()
        emeter = await proto.get_emeter()

        return {
            **self._base_meta(),
            "is_on": bool(sysinfo.get("relay_state", 0)),
            "is_online": True,
            "protection_active": True,
            "surge_count": None,
            "max_voltage_recorded": emeter.get("voltage_v"),
            "protection_joules": None,
        }

    async def get_device_info(self) -> dict[str, Any]:
        if self._is_mock():
            return {
                "model": "P300",
                "mac": None,
                "firmware": "2.0.1",
                "plug_type": "surge_protector",
                "protocol": "kasa",
            }
        proto = self.get_protocol()
        return await proto.get_device_info()


PlugAdapterRegistry.register("surge_protector", SurgeProtectorPlugAdapter)