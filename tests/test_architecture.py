from pathlib import Path

ROOT=Path(__file__).parents[1]


def sources():
    return [p for p in ROOT.rglob("*") if p.is_file() and ".venv" not in p.parts and p.suffix.lower() in {".py",".js",".html",".css",".json",".md",".yaml",".txt"}]


def test_forbidden_frameworks_and_persistence_absent():
    text="\n".join(p.read_text("utf-8",errors="ignore") for p in sources() if "tests" not in p.parts).lower()
    for forbidden in ("react", "next.js", "tailwind", "bootstrap", "localstorage", "sessionstorage", "indexeddb", "document.cookie", "console.log", "ollama", "celery", "redis", "kafka", "localhost:11434"):
        assert forbidden not in text


def test_no_source_secret_or_owner_key_environment():
    text="\n".join(p.read_text("utf-8",errors="ignore") for p in sources() if "tests" not in p.parts)
    assert "TEST_SECRET_DO_NOT_PERSIST_" not in text
    for token in ("GROQ_API_KEY=", "MISTRAL_API_KEY=", "sk_live_"):assert token not in text


def test_only_four_api_routes():
    from app.main import api
    routes={(r.path,tuple(sorted(r.methods or []))) for r in api.routes if getattr(r,"include_in_schema",True)}
    assert {p for p,_ in routes}=={"/health","/v1/transcriptions","/v1/templates/validate","/v1/documents/docx"}
