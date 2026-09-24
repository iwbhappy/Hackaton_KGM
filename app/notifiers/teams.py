"""Teams Incoming Webhook MessageCard transport."""
from html import escape
import httpx
from app.notifiers.base import BaseNotifier


class TeamsNotifier(BaseNotifier):
    def __init__(self, url: str):
        self.url = url

    def send(self, subject: str, text: str) -> None:
        """Post a summary to the webhook configured by the operator."""
        response = httpx.post(self.url, json={"@type": "MessageCard", "@context": "http://schema.org/extensions",
                               "summary": subject, "title": escape(subject), "text": escape(text)}, timeout=10)
        response.raise_for_status()
        if response.text.strip() not in {"1", "", "Accepted"}:
            raise RuntimeError("Teams отклонил сообщение")
