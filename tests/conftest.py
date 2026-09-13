import io
import os
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["APP_ENV"] = "development"
os.environ["ALLOWED_ORIGINS"] = "http://127.0.0.1:8080"


@pytest.fixture(autouse=True)
def reset_guards():
    import app.main as main
    main.tokens = 5.0
    main.last_refill = 0.0
    main.ready = True
    yield


@pytest.fixture
def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000)
        f.writeframes(b"\0\0" * 800)
    return output.getvalue()


@pytest.fixture
def pair():
    path = ROOT / "frontend/templates/fictional_objection/1.0.0"
    return path.joinpath("template.docx").read_bytes(), path.joinpath("template.json").read_bytes()


@pytest.fixture
def values():
    return (ROOT / "tests/fixtures/fictional_values.json").read_bytes()
