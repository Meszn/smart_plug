"""
Adapter Registry — plug_type → Adapter sınıfı eşlemesi.

Neden Registry pattern?
───────────────────────
Servis katmanı bir Plug nesnesine sahip.
"Bu priz tipi için hangi adapter'ı kullanacağım?" sorusunu
if/elif zincirleriyle çözmek yerine registry'ye sorar.

if plug.plug_type == "basic":           ← KÖTÜ
    adapter = BasicPlugAdapter(plug)
elif plug.plug_type == "energy_monitor":
    adapter = EnergyMonitorPlugAdapter(plug)
...

adapter = PlugAdapterRegistry.get_adapter(plug)  ← İYİ

Yeni tip eklemek:
  PlugAdapterRegistry.register("yeni_tip", YeniTipAdapter)
  → Başka hiçbir kod değişmez.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.base import BasePlugAdapter
    from app.models.plug import Plug

logger = logging.getLogger(__name__)


class PlugAdapterRegistry:
    """
    Singleton benzeri sınıf değişkeniyle çalışır.
    Uygulama boyunca tek bir registry nesnesi vardır.
    """
    _registry: dict[str, type[BasePlugAdapter]] = {}

    @classmethod
    def register(cls, plug_type: str, adapter_class: type[BasePlugAdapter]) -> None:
        """
        Yeni adapter tipini kayıt eder.

        Kullanım:
            PlugAdapterRegistry.register("basic", BasicPlugAdapter)

        Genellikle her adapter dosyasının sonunda çağrılır,
        modül import edildiğinde otomatik kayıt gerçekleşir.
        """
        cls._registry[plug_type] = adapter_class
        logger.debug(f"Adapter kayıt edildi: '{plug_type}' → {adapter_class.__name__}")

    @classmethod
    def get_adapter(cls, plug: Plug) -> BasePlugAdapter:
        """
        Priz tipine göre doğru adapter instance'ını döndürür.

        Raises:
            ValueError: Bilinmeyen plug_type için
        """
        adapter_class = cls._registry.get(plug.plug_type)
        if not adapter_class:
            raise ValueError(
                f"'{plug.plug_type}' tipi için adapter bulunamadı. "
                f"Kayıtlı tipler: {cls.supported_types()}"
            )
        return adapter_class(plug)

    @classmethod
    def get_adapter_class_for_type(cls, plug_type: str) -> type[BasePlugAdapter] | None:
        """
        ORM nesnesi olmadan sadece tip string'i ile adapter sınıfını döndürür.
        Ağ taramasında cihaz modeli belirlendikten sonra kullanılır.
        """
        return cls._registry.get(plug_type)

    @classmethod
    def supported_types(cls) -> list[str]:
        """Kayıtlı tüm priz tiplerini döndürür."""
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, plug_type: str) -> bool:
        return plug_type in cls._registry