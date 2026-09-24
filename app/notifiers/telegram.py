"""Telegram Bot API delivery with escaped HTML."""
from html import escape
import httpx
from app.notifiers.base import BaseNotifier


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str):
        self.token, self.chat_id = token, chat_id

    def send(self, subject: str, text: str) -> None:
        """Send one escaped HTML message and check the Bot API response."""
        response = httpx.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                              json={"chat_id": self.chat_id, "text": f"<b>{escape(subject)}</b>\n{escape(text)}",
                                    "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}, timeout=10)
        response.raise_for_status()
        if not response.json().get("ok"):
            raise RuntimeError("Telegram отклонил сообщение")
