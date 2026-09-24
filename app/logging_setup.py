"""Credential-safe application diagnostics with bounded log size."""
import logging
from logging.handlers import RotatingFileHandler

from app.audit import redact
from app.config import settings


class SecretFilter(logging.Filter):
    def filter(self, record) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.msg += "\n" + redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
            record.exc_text = None
        return True


def configure_logging() -> None:
    """Install a UTF-8 rotating file handler once per application process."""
    logger = logging.getLogger("radar")
    if logger.handlers:
        return
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(settings.log_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.addFilter(SecretFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
