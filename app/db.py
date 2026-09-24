"""Database lifecycle and session factory."""
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.config import DEFAULTS, settings
from app.models import Base, Setting

settings.data_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{(settings.data_dir / 'radar.db').as_posix()}",
                       connect_args={"check_same_thread": False, "timeout": 30})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def configure_sqlite(connection, _record) -> None:
    """Enable foreign keys and permit readers while a scan writes."""
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")


def init_db() -> None:
    """Create missing tables and default settings without overwriting user data."""
    settings.trusted_ca_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as session:
        for key, value in DEFAULTS.items():
            if session.get(Setting, key) is None:
                session.add(Setting(key=key, value=value))


def get_settings(session) -> dict:
    """Read all non-secret application settings."""
    return {row.key: row.value for row in session.scalars(select(Setting))}
