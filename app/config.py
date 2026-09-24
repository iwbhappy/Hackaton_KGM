"""Environment settings; credentials are never persisted in the database."""
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    host: str = "127.0.0.1"
    port: int = 8000
    public_url: str = "http://127.0.0.1:8000"
    data_dir: Path = ROOT / "data"
    log_dir: Path = ROOT / "logs"
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_to: str = ""
    teams_webhook_url: SecretStr = SecretStr("")

    @field_validator("data_dir", "log_dir")
    @classmethod
    def absolute_path(cls, value: Path) -> Path:
        """Resolve relative paths against the project, independently from cwd."""
        return value if value.is_absolute() else ROOT / value

    @property
    def trusted_ca_dir(self) -> Path:
        """Return the directory of additional trust anchors."""
        return self.data_dir / "trusted_ca"


settings = Settings()
DEFAULTS = {
    "threshold_info": 60, "threshold_warning": 30, "threshold_critical": 14,
    "notification_thresholds": [60, 30, 14, 7, 1],
    "concurrency": 32, "connect_timeout": 4.0,
    "max_cidr_hosts": 1024, "max_targets": 2048,
    "risk_weights": {"expired": 80, "7": 70, "14": 55, "30": 35, "60": 15,
                     "self_signed": 20, "chain": 25, "hostname": 25,
                     "crypto": 15, "no_owner": 10},
    "risk_multipliers": {"low": 0.85, "normal": 1.0, "high": 1.15, "critical": 1.3},
}
