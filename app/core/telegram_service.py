"""
Telegram bildirim servisi.
"""
import asyncio
import logging
import httpx


from app.core.config import get_settings
settings = get_settings()

logger = logging.getLogger(__name__)


class TelegramService:

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send(self, message: str) -> bool:
        """Telegram'a mesaj gönderir."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram token veya chat_id ayarlanmamış")
            return False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=10.0,
                )
                return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")
            return False

    async def send_alarm(
        self,
        plug_name: str,
        plug_ip: str,
        alarm_type: str,
        value: str,
    ) -> None:
        """Alarm bildirimi gönderir."""
        icons = {
            "high_watt":  "⚡",
            "offline":    "🔴",
            "online":     "🟢",
            "turned_off": "⚫",
            "turned_on":  "🟡",
        }
        icon = icons.get(alarm_type, "⚠️")

        messages = {
            "high_watt":  f"{icon} <b>Yüksek Güç Tüketimi</b>\nPriz: {plug_name}\nIP: {plug_ip}\nAnlık: <b>{value} W</b>",
            "offline":    f"{icon} <b>Cihaz Çevrimdışı</b>\nPriz: {plug_name}\nIP: {plug_ip}\nSüre: {value} dakikadır erişilemiyor",
            "online":     f"{icon} <b>Cihaz Tekrar Çevrimiçi</b>\nPriz: {plug_name}\nIP: {plug_ip}",
            "turned_off": f"{icon} <b>Priz Kapandı</b>\nPriz: {plug_name}\nIP: {plug_ip}",
            "turned_on":  f"{icon} <b>Priz Açıldı</b>\nPriz: {plug_name}\nIP: {plug_ip}",
        }

        message = messages.get(alarm_type, f"{icon} Alarm: {plug_name} — {value}")
        await self.send(message)


# Singleton
telegram = TelegramService()