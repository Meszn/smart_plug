"""
Provision Protokolü — Fabrika çıkışı prizi WiFi'a bağlar.

Akış:
  1. Priz kendi AP'ini yayınlar: "TP-Link_XXXX" (şifresiz)
  2. Bu AP'e bağlan
  3. Prize ağ taraması yaptır → mevcut WiFi'ları listele
  4. Hedef SSID + şifreyi prize gönder
  5. Priz ev ağına bağlanır

Protokol:
  - Kasa (HS serisi): XOR TCP port 9999 — aynı protokol
  - Tapo (P serisi): KLAP HTTP — farklı protokol

Priz AP modundayken IP her zaman sabit:
  - Kasa: 192.168.0.1
  - Tapo: 192.168.0.1
"""
import asyncio
import json
import socket
import struct
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Priz AP modundayken sabit IP
PLUG_AP_IP = "192.168.0.1"
PLUG_AP_PORT = 9999


class ProvisionProtocol:
    """
    Fabrika modundaki Kasa/HS serisi prizi WiFi'a bağlar.
    XOR TCP protokolü kullanır — aynı KasaProtocol mantığı.
    """

    def __init__(self, plug_ip: str = PLUG_AP_IP, timeout: float = 5.0):
        self.plug_ip = plug_ip
        self.timeout = timeout

    # ── XOR şifreleme ─────────────────────────────────────

    @staticmethod
    def _xor_encrypt(data: bytes) -> bytes:
        key = 171
        result = bytearray()
        for byte in data:
            key = byte ^ key
            result.append(key)
        return bytes(result)

    @staticmethod
    def _xor_decrypt(data: bytes) -> bytes:
        key = 171
        result = bytearray()
        for byte in data:
            decrypted = byte ^ key
            result.append(decrypted)
            key = byte
        return bytes(result)

    # ── TCP iletişim ──────────────────────────────────────

    async def _send_command(self, command: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, command)

    def _send_sync(self, command: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(command).encode("utf-8")
        encrypted = self._xor_encrypt(payload)
        packet = struct.pack(">I", len(encrypted)) + encrypted

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect((self.plug_ip, PLUG_AP_PORT))
            sock.sendall(packet)

            header = sock.recv(4)
            if len(header) < 4:
                raise ConnectionError("Geçersiz header")

            expected_len = struct.unpack(">I", header)[0]
            data = b""
            while len(data) < expected_len:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

        return json.loads(self._xor_decrypt(data).decode("utf-8"))

    # ── Provision işlemleri ───────────────────────────────

    async def get_sysinfo(self) -> dict[str, Any]:
        """Priz bilgilerini çeker — model, MAC, vs."""
        result = await self._send_command({"system": {"get_sysinfo": {}}})
        return result.get("system", {}).get("get_sysinfo", {})

    async def scan_wifi(self) -> list[dict[str, Any]]:
        """
        Prizin etrafındaki WiFi ağlarını tarar.
        Kullanıcıya hangi ağların görünür olduğunu gösterir.
        """
        result = await self._send_command({
            "netif": {"get_scaninfo": {"refresh": 1}}
        })
        networks = result.get("netif", {}).get("get_scaninfo", {})
        ap_list = networks.get("ap_list", [])
        return ap_list

    async def connect_wifi(
        self,
        ssid: str,
        password: str,
        key_type: int = 3,
    ) -> bool:
        """
        Prize WiFi bilgilerini gönderir.

        key_type:
          0 = Şifresiz (open)
          1 = WEP
          2 = WPA
          3 = WPA2 (varsayılan — en yaygın)

        Returns:
            True → komut başarıyla gönderildi
            False → hata oluştu
        """
        logger.info(f"WiFi bağlantı komutu gönderiliyor: SSID='{ssid}'")
        try:
            result = await self._send_command({
                "netif": {
                    "set_stainfo": {
                        "ssid": ssid,
                        "password": password,
                        "key_type": key_type,
                    }
                }
            })
            err_code = result.get("netif", {}).get("set_stainfo", {}).get("err_code", -1)
            success = err_code == 0
            logger.info(f"WiFi komutu sonucu: err_code={err_code}, success={success}")
            return success
        except Exception as e:
            logger.error(f"WiFi komutu hatası: {e}")
            return False

    async def is_reachable(self) -> bool:
        """Prize bağlanılabilir mi kontrol eder."""
        try:
            await self.get_sysinfo()
            return True
        except Exception:
            return False