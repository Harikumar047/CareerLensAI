import os
import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add app to system path so it can be imported in tests
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Disable Hugging Face preloading during test runs
os.environ["TESTING"] = "1"

from app.main import app
from app.config import settings

@pytest.fixture(scope="session", autouse=True)
def setup_test_directories():
    """
    Ensure directories needed for tests exist.
    """
    settings.create_dirs()
    yield

@pytest.fixture
def client():
    """
    TestClient fixture for FastAPI endpoints.
    """
    with TestClient(app) as test_client:
        yield test_client
