"""
Temel Akıllı Priz Adapter'ı (basic).
"""
from typing import Any

from app.adapters.base import BasePlugAdapter
from app.adapters.registry import PlugAdapterRegistry
from app.core.polling import get_mock_response
from app.core.protocols.kasa_protocol import KasaProtocol


class BasicPlugAdapter(BasePlugAdapter):

    def _create_protocol(self) -> KasaProtocol:
        from app.core.config import get_settings
        return KasaProtocol(self.plug.ip_address, get_settings().polling_timeout)

    async def get_status(self) -> dict[str, Any]:
        if self._is_mock():
            raw = get_mock_response("basic")
            return {**self._base_meta(), **raw}

        proto = self.get_protocol()
        sysinfo = await proto.get_sysinfo()

        return {
            **self._base_meta(),
            "is_on": bool(sysinfo.get("relay_state", 0)),
            "is_online": True,
            "uptime_seconds": sysinfo.get("on_time"),
        }

    async def get_device_info(self) -> dict[str, Any]:
        if self._is_mock():
            return {
                "model": "P100",
                "mac": None,
                "firmware": "1.0.13",
                "plug_type": "basic",
                "protocol": "kasa",
            }
        proto = self.get_protocol()
        return await proto.get_device_info()


PlugAdapterRegistry.register("basic", BasicPlugAdapter)