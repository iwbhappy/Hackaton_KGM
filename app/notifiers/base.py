"""Notification interface and credential-safe failure descriptions."""
from abc import ABC, abstractmethod
import httpx


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, subject: str, text: str) -> None:
        """Deliver a plain-text summary, raising on a failed transport."""


def delivery_error(error: Exception) -> str:
    """Never expose URLs, bot tokens or SMTP server responses in errors."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"Канал отклонил запрос (HTTP {error.response.status_code})"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "Таймаут отправки уведомления"
    return "Не удалось отправить уведомление. Проверьте настройки канала и доступность сети."
