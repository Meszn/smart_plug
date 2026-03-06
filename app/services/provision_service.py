
"""
Provision Servisi — Prizi WiFi'a bağlama iş akışı.

Windows'ta WiFi geçişi için netsh kullanılır:
  netsh wlan connect name="TP-Link_XXXX"
  netsh wlan connect name="AsılAğım"

Akış:
  1. Mevcut WiFi profilini kaydet
  2. Prizin AP'ine bağlan (TP-Link_XXXX)
  3. Prize hedef SSID + şifre gönder
  4. Prizi yeniden başlat
  5. Asıl ağa geri dön
  6. Birkaç saniye bekle → priz ağa katılsın
  7. Subnet taraması yap → prizi bul
"""
import asyncio
import logging
import subprocess
import time
from typing import Any

from app.core.protocols.provision_protocol import ProvisionProtocol

logger = logging.getLogger(__name__)


class ProvisionService:

    # ── WiFi yönetimi (Windows netsh) ─────────────────────────────────────

    def get_current_wifi(self) -> str | None:
        """Şu an bağlı olunan WiFi SSID'sini döndürür."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, encoding="utf-8", errors="ignore"
            )
            for line in result.stdout.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        return parts[1].strip()
        except Exception as e:
            logger.error(f"Mevcut WiFi alınamadı: {e}")
        return None

    def get_available_wifi_profiles(self) -> list[str]:
        """
        Windows'ta kayıtlı WiFi profillerini listeler.
        Daha önce bağlanılmış ağlar burada görünür.
        """
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True, text=True, encoding="utf-8", errors="ignore"
            )
            profiles = []
            for line in result.stdout.splitlines():
                if "All User Profile" in line or "Tüm Kullanıcı Profili" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        profiles.append(parts[1].strip())
            return profiles
        except Exception as e:
            logger.error(f"Profil listesi alınamadı: {e}")
            return []

    def connect_to_wifi(self, ssid: str, timeout: int = 15) -> bool:
        """
        Windows netsh ile belirtilen WiFi'a bağlanır.
        Ağın daha önce bağlanılmış (profil kayıtlı) olması gerekir.

        Yeni ağ için (prizin AP'i) add_open_profile() çağrılmalı.
        """
        try:
            logger.info(f"WiFi'a bağlanılıyor: '{ssid}'")
            subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True, check=True
            )
            # Bağlantı kurulana kadar bekle
            for _ in range(timeout):
                time.sleep(1)
                current = self.get_current_wifi()
                if current == ssid:
                    logger.info(f"✅ '{ssid}' ağına bağlandı")
                    return True
            logger.warning(f"'{ssid}' ağına {timeout}s içinde bağlanılamadı")
            return False
        except Exception as e:
            logger.error(f"WiFi bağlantı hatası: {e}")
            return False

    def add_open_wifi_profile(self, ssid: str) -> bool:
        """
        Şifresiz (open) WiFi profili ekler.
        Prizin AP'i şifresiz olduğu için bu gerekli.
        Windows'ta daha önce bağlanılmamış ağa bağlanmak
        için önce profil oluşturmak gerekir.
        """
        profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>open</authentication>
                <encryption>none</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
        </security>
    </MSM>
</WLANProfile>"""

        # Geçici XML dosyasına yaz
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.xml', delete=False,
            encoding='utf-8'
        )
        tmp.write(profile_xml)
        tmp.close()

        try:
            subprocess.run(
                ["netsh", "wlan", "add", "profile", f"filename={tmp.name}"],
                capture_output=True, check=True
            )
            logger.info(f"WiFi profili eklendi: '{ssid}'")
            return True
        except Exception as e:
            logger.error(f"Profil eklenemedi: {e}")
            return False
        finally:
            os.unlink(tmp.name)

    def delete_wifi_profile(self, ssid: str) -> None:
        """Geçici olarak eklenen profili temizler."""
        try:
            subprocess.run(
                ["netsh", "wlan", "delete", "profile", f"name={ssid}"],
                capture_output=True
            )
            logger.info(f"Profil silindi: '{ssid}'")
        except Exception:
            pass

    def scan_nearby_wifi(self) -> list[str]:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, text=True, encoding="utf-8", errors="ignore"
            )
            networks = []
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("SSID") and "BSSID" not in stripped and ":" in stripped:
                    parts = stripped.split(":", 1)
                    if len(parts) == 2:
                        ssid = parts[1].strip()
                        if ssid:
                            networks.append(ssid)
            return networks
        except Exception as e:
            logger.error(f"WiFi tarama hatası: {e}")
            return []

    # ── Ana provision akışı ───────────────────────────────────────────────

    async def provision_plug(
        self,
        plug_ap_ssid: str,
        target_ssid: str,
        target_password: str,
        original_ssid: str | None = None,
    ) -> dict[str, Any]:
        """
        Fabrika modundaki prizi hedef WiFi'a bağlar.

        Args:
            plug_ap_ssid    : Prizin yayınladığı AP adı (örn: "TP-Link_EC A5")
            target_ssid     : Prizin bağlanacağı WiFi (ev/ofis ağı)
            target_password : Hedef WiFi şifresi
            original_ssid   : Geri dönülecek ağ (None ise otomatik tespit)

        Returns:
            {
                "success": bool,
                "plug_ip": str | None,    # Yeni IP (bulunursa)
                "model": str | None,
                "message": str,
                "steps": [...]            # Her adımın sonucu
            }
        """
        steps = []

        # Mevcut ağı kaydet
        if not original_ssid:
            original_ssid = self.get_current_wifi()
        steps.append({"step": "Mevcut ağ", "value": original_ssid or "Bilinmiyor"})
        logger.info(f"Provision başlıyor. Mevcut ağ: '{original_ssid}'")

        try:
            # ── ADIM 1: Prizin AP'ine profil ekle ────────
            steps.append({"step": "Profil ekleniyor", "value": plug_ap_ssid})
            self.add_open_wifi_profile(plug_ap_ssid)

            # ── ADIM 2: Prizin AP'ine bağlan ─────────────
            steps.append({"step": "Priz AP'ine bağlanılıyor", "value": plug_ap_ssid})
            connected = self.connect_to_wifi(plug_ap_ssid, timeout=20)
            if not connected:
                return {
                    "success": False,
                    "plug_ip": None,
                    "model": None,
                    "message": f"Prizin AP'ine bağlanılamadı: '{plug_ap_ssid}'",
                    "steps": steps,
                }
            steps.append({"step": "Priz AP bağlantısı", "value": "✅ Başarılı"})

            # ── ADIM 3: Prizi tanı ────────────────────────
            await asyncio.sleep(2)
            proto = ProvisionProtocol(timeout=5.0)
            try:
                sysinfo = await proto.get_sysinfo()
                model = sysinfo.get("model", "Bilinmiyor")
                steps.append({"step": "Cihaz modeli", "value": model})
                logger.info(f"Cihaz tespit edildi: {model}")
            except Exception:
                model = "Bilinmiyor"
                steps.append({"step": "Cihaz modeli", "value": "Tespit edilemedi"})

            # ── ADIM 4: Hedef WiFi'ı prize gönder ────────
            steps.append({"step": "WiFi bilgisi gönderiliyor", "value": target_ssid})
            success = await proto.connect_wifi(target_ssid, target_password)
            if not success:
                return {
                    "success": False,
                    "plug_ip": None,
                    "model": model,
                    "message": "WiFi bilgisi prize gönderilemedi",
                    "steps": steps,
                }
            steps.append({"step": "WiFi komutu", "value": "✅ Gönderildi"})

            # ── ADIM 5: Asıl ağa geri dön ────────────────
            await asyncio.sleep(2)
            if original_ssid:
                steps.append({"step": "Asıl ağa dönülüyor", "value": original_ssid})
                self.connect_to_wifi(original_ssid, timeout=20)
                steps.append({"step": "Asıl ağ bağlantısı", "value": "✅ Geri döndü"})

            # Geçici profili temizle
            self.delete_wifi_profile(plug_ap_ssid)

            # ── ADIM 6: Prizi ağda bul ────────────────────
            steps.append({"step": "Priz aranıyor", "value": "Subnet taranıyor..."})
            await asyncio.sleep(8)  # Prize bağlanma süresi tanı

            plug_ip = await self._find_new_plug(target_ssid)
            if plug_ip:
                steps.append({"step": "Priz bulundu", "value": plug_ip})
                logger.info(f"✅ Priz bulundu: {plug_ip}")
            else:
                steps.append({"step": "Priz arama", "value": "Bulunamadı — manuel tarama gerekebilir"})

            return {
                "success": True,
                "plug_ip": plug_ip,
                "model": model,
                "message": f"Priz '{target_ssid}' ağına başarıyla bağlandı!",
                "steps": steps,
            }

        except Exception as e:
            logger.error(f"Provision hatası: {e}", exc_info=True)
            # Hata olsa bile asıl ağa dön
            if original_ssid:
                try:
                    self.connect_to_wifi(original_ssid, timeout=15)
                except Exception:
                    pass
            return {
                "success": False,
                "plug_ip": None,
                "model": None,
                "message": f"Provision hatası: {str(e)}",
                "steps": steps,
            }

    async def _find_new_plug(self, target_ssid: str) -> str | None:
        """
        Provision sonrası prizi ağda bulmaya çalışır.
        Mevcut IP adresinden subnet'i tahmin eder ve tarar.
        """
        import socket as sock_module
        try:
            # Kendi IP'mizi al → subnet belirle
            hostname = sock_module.gethostname()
            local_ip = sock_module.gethostbyname(hostname)
            subnet = '.'.join(local_ip.split('.')[:3])
            logger.info(f"Yeni priz aranıyor: {subnet}.x")

            from app.core.protocols.kasa_protocol import KasaProtocol
            semaphore = asyncio.Semaphore(50)

            async def probe(ip: str) -> str | None:
                async with semaphore:
                    try:
                        proto = KasaProtocol(ip, timeout=1.0)
                        sysinfo = await proto.get_sysinfo()
                        device_type = sysinfo.get("type", "")
                        if "SMARTPLUG" in device_type.upper():
                            return ip
                    except Exception:
                        pass
                    return None

            tasks = [probe(f"{subnet}.{i}") for i in range(1, 255)]
            results = await asyncio.gather(*tasks)
            found = [r for r in results if r is not None]
            return found[0] if found else None

        except Exception as e:
            logger.error(f"Priz arama hatası: {e}")
            return None

    def get_tp_link_networks(self) -> list[str]:
        all_networks = self.scan_nearby_wifi() or []
        return [n for n in all_networks if "tp-link" in n.lower() or "tp_link" in n.lower()]