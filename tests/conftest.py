from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest


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
