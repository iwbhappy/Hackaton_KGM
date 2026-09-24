from pathlib import Path
from threading import Thread
from uuid import uuid4
import os

import pytest

# Test databases and logs never modify the user's application state.
TEST_ROOT = Path(__file__).resolve().parent.parent / ".test-artifacts" / uuid4().hex
os.environ["DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["LOG_DIR"] = str(TEST_ROOT / "logs")
for name in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_TO", "TEAMS_WEBHOOK_URL"]:
    os.environ[name] = ""


@pytest.fixture(scope="session")
def workspace():
    path = Path(__file__).resolve().parent.parent / ".test-artifacts" / uuid4().hex
    path.mkdir(parents=True)
    return path


@pytest.fixture(scope="session")
def lab_material(workspace):
    from lab.generate_certs import generate
    folder, trust = workspace / "certs", workspace / "trust"
    generate(folder, trust)
    return folder, trust


@pytest.fixture(scope="session")
def lab_server(lab_material):
    from lab.lab_server import LabServer
    server = LabServer(("127.0.0.1", 0), lab_material[0])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.db import engine, init_db
    from app.main import app
    engine.dispose()
    database = Path(engine.url.database).resolve()
    assert database.is_relative_to(TEST_ROOT.resolve()) and database.name == "radar.db"
    database.unlink(missing_ok=True)
    from app.scanner import PROGRESS
    PROGRESS.clear()
    init_db()
    with TestClient(app) as test_client:
        yield test_client
