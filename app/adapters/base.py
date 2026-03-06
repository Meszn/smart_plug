"""
Soyut Adapter — Protokolden bağımsız priz arayüzü.

Adapter'lar protokol detayını bilmez:
  - KasaProtocol mu kullanıyor?
  - TapoProtocol mu?
  → Fark yok, ikisi de aynı BaseProtocol arayüzünü sunar.
"""
import abc
from typing import Any

from app.core.protocols.base_protocol import BaseProtocol
from app.models.plug import Plug
from app.schemas.plug import ActionResponse, ActionType


class BasePlugAdapter(abc.ABC):

    def __init__(self, plug: Plug) -> None:
        self.plug = plug
        self._protocol: BaseProtocol | None = None

    @abc.abstractmethod
    def _create_protocol(self) -> BaseProtocol:
        """
        Cihaz tipine uygun protokol nesnesi oluşturur.
        Her adapter kendi protokolünü bilir:
          HS110Adapter → KasaProtocol
          TapoP110Adapter → TapoProtocol
        """
        ...

    def get_protocol(self) -> BaseProtocol:
        """Protokol nesnesini lazy olarak oluşturur (singleton per request)."""
        if self._protocol is None:
            self._protocol = self._create_protocol()
        return self._protocol

    def _is_mock(self) -> bool:
        return self.plug.ip_address.lower().startswith("mock")

    def _base_meta(self) -> dict[str, Any]:
        return {
            "plug_id": self.plug.id,
            "plug_type": self.plug.plug_type,
            "name": self.plug.name,
            "ip_address": self.plug.ip_address,
        }

    @abc.abstractmethod
    async def get_status(self) -> dict[str, Any]:
        """Cihazdan anlık durum çeker."""
        ...

    @abc.abstractmethod
    async def get_device_info(self) -> dict[str, Any]:
        """Tarama için cihaz kimlik bilgisi."""
        ...

    async def turn_on(self) -> ActionResponse:
        return await self._execute_relay(True, ActionType.TURN_ON, "açıldı")

    async def turn_off(self) -> ActionResponse:
        return await self._execute_relay(False, ActionType.TURN_OFF, "kapatıldı")

    async def restart(self) -> ActionResponse:
        """Kapat → bekle → aç."""
        if self._is_mock():
            return ActionResponse(
                success=True, action=ActionType.RESTART,
                plug_id=self.plug.id, plug_name=self.plug.name,
                message=f"[Mock] '{self.plug.name}' yeniden başlatıldı.",
                device_response={"simulated": True},
            )
        try:
            proto = self.get_protocol()
            await proto.set_relay(False)
            import asyncio
            await asyncio.sleep(2)
            await proto.set_relay(True)
            return ActionResponse(
                success=True, action=ActionType.RESTART,
                plug_id=self.plug.id, plug_name=self.plug.name,
                message=f"'{self.plug.name}' yeniden başlatıldı.",
                device_response={"restarted": True},
            )
        except Exception as e:
            return ActionResponse(
                success=False, action=ActionType.RESTART,
                plug_id=self.plug.id, plug_name=self.plug.name,
                message=str(e), device_response=None,
            )

    async def _execute_relay(
        self,
        state: bool,
        action: ActionType,
        label: str,
    ) -> ActionResponse:
        if self._is_mock():
            return ActionResponse(
                success=True, action=action,
                plug_id=self.plug.id, plug_name=self.plug.name,
                message=f"[Mock] '{self.plug.name}' {label}.",
                device_response={"simulated": True},
            )
        try:
            proto = self.get_protocol()
            success = await proto.set_relay(state)
            return ActionResponse(
                success=success, action=action,
                plug_id=self.plug.id, plug_name=self.plug.name,
                message=f"'{self.plug.name}' {label}." if success else "Komut başarısız.",
                device_response={"state": state},
            )
        except Exception as e:
            return ActionResponse(
                success=False, action=action,
                plug_id=self.plug.id, plug_name=self.plug.name,
                message=str(e), device_response=None,
            )