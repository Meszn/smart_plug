"""
Soyut Protokol Temel Sınıfı.

Her fiziksel iletişim protokolü bu sınıftan türer:
  - KasaProtocol  → HS110/HS100 XOR TCP (port 9999)
  - TapoProtocol  → P100/P110 KLAP HTTP (port 80)

Adapter'lar protokolü bilmez — sadece get_sysinfo(),
get_emeter(), set_relay() çağırır. Protokol farkı
bu katmanda soyutlanır.
"""
import abc
from typing import Any


class BaseProtocol(abc.ABC):

    def __init__(self, ip: str, timeout: float = 5.0):
        self.ip = ip
        self.timeout = timeout

    @abc.abstractmethod
    async def get_sysinfo(self) -> dict[str, Any]:
        """Cihaz sistem bilgisi — model, mac, relay_state, vs."""
        ...

    @abc.abstractmethod
    async def get_emeter(self) -> dict[str, Any]:
        """
        Enerji ölçüm verisi.
        Desteklemeyen cihazlar boş dict döner.
        """
        ...

    @abc.abstractmethod
    async def set_relay(self, state: bool) -> bool:
        """
        Prizi aç (True) veya kapat (False).
        Başarılı ise True döner.
        """
        ...

    @abc.abstractmethod
    async def get_device_info(self) -> dict[str, Any]:
        """
        Tarama için cihaz kimlik bilgileri.
        Returns: {model, mac, firmware, device_type}
        """
        ...