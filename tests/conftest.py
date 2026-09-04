import os
from pathlib import Path

TEST_ROOT = Path(__file__).parent / ".data"
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = str(TEST_ROOT / "uploads")
os.environ["ALLOWED_EMAIL_DOMAINS"] = "school.edu.cn"
os.environ["ENABLE_BACKGROUND_TASKS"] = "false"
os.environ["SMTP_HOST"] = ""

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
