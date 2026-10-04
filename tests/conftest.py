"""Shared pytest fixtures."""
import io
import os
import sys
import tempfile
from pathlib import Path

# Set testing flags before importing FastAPI app
os.environ["TESTING"] = "true"
os.environ["PYTEST_CURRENT_TEST"] = "true"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["MARKET_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_APP_SECRET"] = ""
os.environ.setdefault("DEMO_MODE", "auto")

import pytest                                  # noqa: E402
from fastapi.testclient import TestClient      # noqa: E402
from PIL import Image                           # noqa: E402

from app.rate_limit import limiter              # noqa: E402

# Disable rate-limiting during pytest execution
limiter.enabled = False

SAMPLES = ROOT / "tests" / "samples"


def make_image_bytes(color=(60, 140, 70), size=(300, 300), fmt="JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:                  # runs lifespan => loads model once
        yield c


@pytest.fixture
def leaf_bytes():
    return make_image_bytes()


@pytest.fixture
def fake_model(monkeypatch):
    from app.model import classifier

    def _set(class_name: str, confidence: float):
        monkeypatch.setattr(classifier, "predict", lambda batch, image_bytes=b"": (class_name, confidence, 1.0))
        monkeypatch.setattr(classifier, "mode", "real")
    return _set