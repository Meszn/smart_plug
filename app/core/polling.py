"""
HTTP Polling İstemcisi.

İki temel işlev:
  1. fetch_plug_data()    → Cihazdan durum çek (GET)
  2. send_plug_command()  → Cihaza komut gönder (POST)

Hata sınıfları:
  PlugOfflineError   → Cihaza ulaşılamıyor (timeout, bağlantı reddedildi)
  PlugResponseError  → Cihaz yanıt verdi ama içerik hatalı
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5.0


async def fetch_plug_data(
    ip_address: str,
    endpoint: str = "/status",
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Cihaza GET isteği atar, JSON yanıtı döndürür.

    Args:
        ip_address : Prizin IP adresi (örn: "192.168.1.101")
        endpoint   : Cihazın endpoint'i (örn: "/status")
        timeout    : Maksimum bekleme süresi (saniye)
    """
    url = f"http://{ip_address}{endpoint}"
    logger.debug(f"Polling → {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    except httpx.ConnectTimeout:
        raise PlugOfflineError(ip_address, "Bağlantı zaman aşımı")
    except httpx.ConnectError:
        raise PlugOfflineError(ip_address, "Cihaz kapalı veya erişilemiyor")
    except httpx.HTTPStatusError as e:
        raise PlugResponseError(ip_address, f"HTTP {e.response.status_code}")
    except Exception as e:
        raise PlugResponseError(ip_address, str(e))


async def send_plug_command(
    ip_address: str,
    command_path: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Cihaza POST komutu gönderir.

    Örnek: send_plug_command("192.168.1.101", "/cmd/on")
    """
    url = f"http://{ip_address}{command_path}"
    logger.info(f"Komut → {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url)
            response.raise_for_status()
            return response.json()

    except httpx.ConnectTimeout:
        raise PlugOfflineError(ip_address, "Komut zaman aşımı")
    except httpx.ConnectError:
        raise PlugOfflineError(ip_address, "Cihaza bağlanılamadı")
    except httpx.HTTPStatusError as e:
        raise PlugResponseError(ip_address, f"Komut hatası HTTP {e.response.status_code}")
    except Exception as e:
        raise PlugResponseError(ip_address, str(e))


# ── Hata sınıfları ────────────────────────────────────────

class PlugOfflineError(Exception):
    """Fiziksel cihaza ulaşılamadığında."""
    def __init__(self, ip: str, reason: str = "Bilinmiyor"):
        self.ip = ip
        self.reason = reason
        super().__init__(f"Cihaz çevrimdışı [{ip}]: {reason}")


class PlugResponseError(Exception):
    """Cihaz yanıt verdi ama yanıt geçersiz."""
    def __init__(self, ip: str, detail: str):
        self.ip = ip
        self.detail = detail
        super().__init__(f"Geçersiz yanıt [{ip}]: {detail}")


# ── Mock (Geliştirme ortamı simülasyonu) ─────────────────
# ip_address "mock" ile başlıyorsa gerçek HTTP isteği atılmaz.

MOCK_RESPONSES: dict[str, dict[str, Any]] = {
    "basic": {
        "is_on": True,
        "is_online": True,
        "uptime_seconds": 3600,
    },
    "energy_monitor": {
        "is_on": True,
        "is_online": True,
        "current_watt": 142.5,
        "voltage": 221.3,
        "current_ampere": 0.64,
        "total_kwh": 18.92,
        "power_factor": 0.96,
    },
    "surge_protector": {
        "is_on": True,
        "is_online": True,
        "protection_active": True,
        "surge_count": 3,
        "max_voltage_recorded": 243.1,
        "protection_joules": 1080,
    },
}


def get_mock_response(plug_type: str) -> dict[str, Any]:
    """Geliştirme ortamı için sahte veri döner."""
    return dict(MOCK_RESPONSES.get(plug_type, {"is_on": False, "is_online": False}))