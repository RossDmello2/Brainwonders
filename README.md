# Cloud Legal Stenographer

An anonymous, stateless speech/audio-to-DOCX web utility implemented from the adjacent specification pack. The frontend is plain HTML, CSS and JavaScript. FastAPI relays one visitor-owned provider key for one transcription request and generates DOCX files from temporary paired DOCX/JSON templates. The PDF path is the semantic preview plus the browser's **Print / Save as PDF** command.

The included legal layouts and data are fictional test examples. This application gives no legal advice, creates no accounts, stores no document history, signs nothing and files nothing.

## Local development

Python 3.12.6 was used for the verified local run.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:APP_ENV='development'
$env:ALLOWED_ORIGINS='http://127.0.0.1:8080'
$env:PYTHONPATH=(Resolve-Path backend)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal:

```powershell
python -m http.server 8080 --directory frontend
```

Open `http://127.0.0.1:8080`. Automated tests never contact transcription providers:

```powershell
$env:PYTHONPATH=(Resolve-Path backend)
.venv\Scripts\python.exe -m pytest tests -q
```

## Template assets

Built-ins live at `frontend/templates/<id>/<version>/template.docx` and `template.json`; `frontend/templates/index.json` is the only catalog. The backend has no built-in template registry. Run `scripts/materialize_templates.py` to reproduce the two fictional assets directly from the immutable specification pack. Adding a new schema-v1 pair changes assets and the manifest only.

Uploaded pairs are held in the page and resent for every validation/generation request. The backend validates exact bytes, safe OOXML structure, restricted tags, content parity, layout, typed values, filename and fingerprint; rendering occurs in a killable request-owned child. No template URL, result URL or server session exists.

Deployment and its unresolved account/host gates are in [deployment/README.md](deployment/README.md). Current external checks are in [docs/external-verification.md](docs/external-verification.md). The original specification pack remains unchanged.
