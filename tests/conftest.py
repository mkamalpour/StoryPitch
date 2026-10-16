"""Use temporary storage and exclude legacy live-service scripts from pytest."""

import os
from pathlib import Path
import sys
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_runtime = tempfile.TemporaryDirectory(prefix="storypitch-tests-")
os.environ.update(
    DATABASE_URL="sqlite:///" + str(Path(_runtime.name) / "test.db"),
    STORYPITCH_LOG_DIR=str(Path(_runtime.name) / "logs"),
    DEFAULT_MODEL="fallback",
    OFFLINE_MODE="true",
    LOG_LEVEL="WARNING",
)
collect_ignore = ["manual"]


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    from sqlmodel import SQLModel, create_engine
    from sqlalchemy.pool import StaticPool
    from db import db
    from api import main

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "API_KEY", "")
    import api.auth

    monkeypatch.setattr(api.auth, "API_KEY", "")
    SQLModel.metadata.create_all(engine)
    main._session_processing.clear()
    monkeypatch.setattr(main, "_pending_starts", 0)
    yield engine
    engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    import logging

    logging.shutdown()
    _runtime.cleanup()
