"""
Kasa Protokolü — HS110/HS100 XOR TCP iletişimi.

Protokol detayı:
  1. JSON komut → XOR şifrele (başlangıç key=171)
  2. 4 byte big-endian uzunluk header ekle
  3. TCP port 9999'a gönder
  4. Yanıt: 4 byte header + XOR şifreli JSON

Kimlik doğrulama YOK — aynı ağdaki herkes komut gönderebilir.
Şifreleme sadece obfuscation amaçlı, güvenlik değil.

Desteklenen modeller:
  HS100 → temel on/off
  HS110 → on/off + enerji izleme
  HS200, HS300 → diğer Kasa modelleri
"""
import asyncio
import json
import socket
import struct
from typing import Any

from app.core.protocols.base_protocol import BaseProtocol


class KasaProtocol(BaseProtocol):

    # Kasa model → sistem tipi eşlemesi
    # get_device_info() bunu kullanarak plug_type döndürür
    MODEL_TYPE_MAP: dict[str, str] = {
        "HS100": "basic",
        "HS103": "basic",
        "HS105": "basic",
        "HS200": "basic",
        "HS110": "energy_monitor",
        "HS115": "energy_monitor",
        "HS300": "surge_protector",
    }

    # ── XOR şifreleme ─────────────────────────────────────

    @staticmethod
    def _xor_encrypt(data: bytes) -> bytes:
        """
        TP-Link XOR şifreleme.
        Her byte, önceki şifreli byte ile XOR'lanır.
        Başlangıç anahtarı 171 (sabit).
        """
        key = 171
        result = bytearray()
        for byte in data:
            key = byte ^ key
            result.append(key)
        return bytes(result)

    @staticmethod
    def _xor_decrypt(data: bytes) -> bytes:
        """
        TP-Link XOR şifre çözme.
        Her byte, önceki şifreli byte ile XOR'lanır.
        """
        key = 171
        result = bytearray()
        for byte in data:
            decrypted = byte ^ key
            result.append(decrypted)
            key = byte
        return bytes(result)

    # ── TCP iletişim ──────────────────────────────────────

    async def _send_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """
        Cihaza komut gönderir, yanıtı döndürür.

        asyncio.get_event_loop().run_in_executor() kullanılır
        çünkü socket işlemleri bloklayıcı (blocking).
        Bunu executor'a vererek FastAPI'nin async döngüsünü
        bloke etmekten kaçınırız.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Default ThreadPoolExecutor
            self._send_command_sync,
            command,
        )

    def _send_command_sync(self, command: dict[str, Any]) -> dict[str, Any]:
        """Senkron TCP gönderim — executor thread'inde çalışır."""
        payload = json.dumps(command).encode("utf-8")
        encrypted = self._xor_encrypt(payload)
        packet = struct.pack(">I", len(encrypted)) + encrypted

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect((self.ip, 9999))
            sock.sendall(packet)

            # Önce 4 byte header oku → veri uzunluğunu öğren
            header = sock.recv(4)
            if len(header) < 4:
                raise ConnectionError(f"Geçersiz header [{self.ip}]")

            expected_len = struct.unpack(">I", header)[0]

            # Tam veriyi oku
            data = b""
            while len(data) < expected_len:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

        return json.loads(self._xor_decrypt(data).decode("utf-8"))

    # ── BaseProtocol implementasyonu ──────────────────────

    async def get_sysinfo(self) -> dict[str, Any]:
        """Cihaz sistem bilgisini çeker."""
        result = await self._send_command({"system": {"get_sysinfo": {}}})
        return result.get("system", {}).get("get_sysinfo", {})

    async def get_emeter(self) -> dict[str, Any]:
        """
        Enerji tüketim verisi çeker.
        HS100 gibi emeter desteklemeyen cihazlar hata döner,
        bunu yakalayıp boş dict döndürürüz.
        """
        try:
            result = await self._send_command({"emeter": {"get_realtime": {}}})
            emeter = result.get("emeter", {}).get("get_realtime", {})

            # Hata kodu varsa desteklenmiyor
            if emeter.get("err_code", 0) != 0:
                return {}

            # Milisantim → standart birime çevir
            return {
                "voltage_v": emeter.get("voltage_mv", 0) / 1000,
                "current_a": emeter.get("current_ma", 0) / 1000,
                "power_w": emeter.get("power_mw", 0) / 1000,
                "total_kwh": emeter.get("total_wh", 0) / 1000,
            }
        except Exception:
            return {}

    async def set_relay(self, state: bool) -> bool:
        """Prizi aç (True) veya kapat (False)."""
        value = 1 if state else 0
        result = await self._send_command(
            {"system": {"set_relay_state": {"state": value}}}
        )
        err = result.get("system", {}).get("set_relay_state", {}).get("err_code", -1)
        return err == 0

    async def get_device_info(self) -> dict[str, Any]:
        """
        Tarama için cihaz kimlik bilgisi.
        Model adından plug_type otomatik belirlenir.
        """
        sysinfo = await self.get_sysinfo()

        # "HS110(EU)" → "HS110"
        raw_model = sysinfo.get("model", "")
        model_clean = raw_model.split("(")[0].strip()

        plug_type = self.MODEL_TYPE_MAP.get(model_clean, "basic")

        return {
            "model": raw_model,
            "model_clean": model_clean,
            "mac": sysinfo.get("mac", "").replace("-", ":"),
            "firmware": sysinfo.get("sw_ver", ""),
            "alias": sysinfo.get("alias", ""),
            "plug_type": plug_type,
            "protocol": "kasa",
        }