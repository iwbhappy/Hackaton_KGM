"""Read-only channel configuration from environment secrets."""
from app.config import settings
from app.notifiers.email import EmailNotifier
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.teams import TeamsNotifier


def get_notifiers() -> dict:
    """Construct only fully configured delivery channels."""
    channels = {}
    if settings.telegram_bot_token.get_secret_value() and settings.telegram_chat_id:
        channels["telegram"] = TelegramNotifier(settings.telegram_bot_token.get_secret_value(), settings.telegram_chat_id)
    if all([settings.smtp_host, settings.smtp_user, settings.smtp_password.get_secret_value(), settings.smtp_from, settings.smtp_to]):
        channels["email"] = EmailNotifier(settings)
    if settings.teams_webhook_url.get_secret_value():
        channels["teams"] = TeamsNotifier(settings.teams_webhook_url.get_secret_value())
    return channels


def mask(value: str) -> str:
    """Mask configured values; keep short values completely hidden."""
    return value[:5] + "****" if len(value) > 9 else "****" if value else "не настроено"


def channel_status() -> dict:
    """Expose configuration state and masked credentials only."""
    active = get_notifiers()
    values = {"telegram": settings.telegram_bot_token.get_secret_value(),
              "email": settings.smtp_password.get_secret_value(), "teams": settings.teams_webhook_url.get_secret_value()}
    return {name: {"configured": name in active, "masked": mask(value)} for name, value in values.items()}
