"""Four-route anonymous API with bounded, stateless request ownership."""
from __future__ import annotations

import asyncio
import re
import threading
import time
import uuid
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from .contracts import TranscriptionForm
from .errors import AppError, MESSAGES, error_response
from .middleware import RequestPolicyMiddleware
from .providers import PROVIDERS, relay_transcription
from .safe_logging import configure_logging, outcome
from .services.audio import inspect_audio
from .services.document_isolation import run_isolated
from .settings import AUDIO_MAX, CONFIG_MAX, DOCX_MAX, VALUES_MAX, Settings

settings = Settings.from_env()
api = FastAPI(title="Cloud Legal Stenographer API", docs_url=None, redoc_url=None, openapi_url=None)
api.add_middleware(RequestPolicyMiddleware, origins=settings.origins)
configure_logging()
heavy = asyncio.Semaphore(1)
tokens, last_refill = 5.0, time.monotonic()
ready = True


def _request_id(request):
    return getattr(request.state, "request_id", str(uuid.uuid4()))


@api.exception_handler(AppError)
async def app_error(request, exc):
    outcome(_request_id(request), request.scope.get("route").path if request.scope.get("route") else "unknown", exc.status, exc.code)
    return error_response(exc, _request_id(request))


@api.exception_handler(RequestValidationError)
@api.exception_handler(ValidationError)
async def validation_error(request, _exc):
    return error_response(AppError("REQUEST_INVALID", 400), _request_id(request))


@api.exception_handler(Exception)
async def unexpected_error(request, _exc):
    return error_response(AppError("REQUEST_FAILED", 500), _request_id(request))


def _guard_query_and_key(request, allow_key=False):
    if request.url.query: raise AppError("REQUEST_INVALID", 400)
    key_headers = [value for name, value in request.scope["headers"] if name.lower() == b"x-provider-key"]
    if len(key_headers) > 1 or (not allow_key and key_headers): raise AppError("REQUEST_INVALID", 400)


async def _capacity():
    global tokens, last_refill
    now = time.monotonic(); tokens = min(5, tokens + (now-last_refill) * .5); last_refill = now
    if tokens < 1: raise AppError("SERVICE_RATE_LIMITED", 429, retryable=True)
    tokens -= 1
    if heavy.locked(): raise AppError("SERVICE_BUSY", 503, retryable=True)
    await heavy.acquire()


def _exact_parts(form, expected):
    names = [key for key, _ in form.multi_items()]
    if len(names) != len(expected) or set(names) != expected or len(names) != len(set(names)):
        raise AppError("REQUEST_INVALID", 400)


async def _document_work(operation, payload):
    canceled = threading.Event()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(run_isolated, operation, payload, 25, canceled),
            timeout=settings.document_seconds)
    finally:
        canceled.set()


async def _read(upload, maximum):
    global ready
    try:
        data = await upload.read(maximum + 1)
        if len(data) > maximum: raise AppError("INPUT_TOO_LARGE", 413)
        return data
    finally:
        try:
            await upload.close()
        except Exception:
            ready = False
            raise AppError("CLEANUP_FAILED", 503)


@api.get("/health")
async def health(request: Request):
    _guard_query_and_key(request)
    if not ready: raise AppError("SERVICE_NOT_READY", 503)
    return {"status": "ok", "api_version": "1", "template_schema_versions": ["1.0"]}


@api.post("/v1/transcriptions")
async def transcribe(request: Request):
    _guard_query_and_key(request, allow_key=True)
    await _capacity()
    key = request.headers.get("x-provider-key")
    try:
        if key is None: raise AppError("PROVIDER_KEY_REQUIRED", 422)
        if not 1 <= len(key) <= 512 or any(ord(c) < 33 or ord(c) > 126 or c.isspace() for c in key):
            raise AppError("PROVIDER_KEY_INVALID", 422)
        async with request.form(max_files=1, max_fields=6, max_part_size=1024) as form:
            expected = {"audio", "provider", "model", "capture_source", "duration_unknown_acknowledged"}
            if "language" in form: expected.add("language")
            if "client_duration_seconds" in form: expected.add("client_duration_seconds")
            _exact_parts(form, expected)
            if not isinstance(form["audio"], UploadFile): raise AppError("REQUEST_INVALID", 400)
            fields = {name: form.get(name) for name in expected if name != "audio"}
            try: parsed = TranscriptionForm.model_validate(fields)
            except (ValidationError, ValueError): raise AppError("REQUEST_INVALID", 400)
            provider = PROVIDERS.get(parsed.provider)
            if not provider or parsed.model not in provider.models: raise AppError("MODEL_UNAVAILABLE", 503)
            if parsed.language and not re.fullmatch(r"[a-z]{2}", parsed.language): raise AppError("REQUEST_INVALID", 400)
            audio = await _read(form["audio"], AUDIO_MAX)
        extension, duration = inspect_audio(audio)
        if duration is None and parsed.duration_unknown_acknowledged != "true": raise AppError("REQUEST_INVALID", 400)
        text, detected = await relay_transcription(parsed.provider, parsed.model, key, audio, extension, parsed.language,
                                                    transport=getattr(request.app.state, "provider_transport", None))
        warnings = []
        if duration is None: warnings.append({"code":"DURATION_UNVERIFIED", "message":"Audio duration could not be verified."})
        if parsed.language and detected and parsed.language != detected:
            warnings.append({"code":"LANGUAGE_MISMATCH", "message":"The provider detected a different language. Review the transcript carefully."})
        elif not detected: warnings.append({"code":"LANGUAGE_NOT_CONFIRMED", "message":"The provider did not confirm the audio language."})
        warnings.append({"code":"REVIEW_REQUIRED", "message":"Review every word before using the transcript."})
        return {"request_id": _request_id(request), "provider": parsed.provider, "model": parsed.model,
            "text": text, "language": {"requested": parsed.language, "detected": detected},
            "audio": {"bytes":len(audio), "duration_seconds": duration,
                      "duration_source":"server_metadata" if duration is not None else "unavailable"}, "warnings":warnings}
    finally:
        key = None
        heavy.release()


@api.post("/v1/templates/validate")
async def validate_template(request: Request):
    _guard_query_and_key(request); await _capacity()
    try:
        async with request.form(max_files=2, max_fields=0, max_part_size=1024) as form:
            _exact_parts(form, {"template_docx", "template_json"})
            if not all(isinstance(form[x], UploadFile) for x in ("template_docx", "template_json")): raise AppError("TEMPLATE_PAIR_REQUIRED", 422)
            docx, config = await asyncio.gather(_read(form["template_docx"], DOCX_MAX), _read(form["template_json"], CONFIG_MAX))
        result = await _document_work("validate", {"docx":docx,"config":config})
        return {"request_id":_request_id(request), **result}
    finally: heavy.release()


@api.post("/v1/documents/docx")
async def document(request: Request):
    _guard_query_and_key(request); await _capacity()
    try:
        async with request.form(max_files=3, max_fields=2, max_part_size=VALUES_MAX) as form:
            _exact_parts(form, {"template_docx","template_json","values_json","expected_fingerprint","review_confirmed"})
            if form["review_confirmed"] != "true": raise AppError("REVIEW_REQUIRED", 422)
            fingerprint = form["expected_fingerprint"]
            if not isinstance(fingerprint,str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint): raise AppError("REQUEST_INVALID", 400)
            if not all(isinstance(form[x], UploadFile) for x in ("template_docx","template_json","values_json")): raise AppError("REQUEST_INVALID", 400)
            docx, config, values = await asyncio.gather(_read(form["template_docx"], DOCX_MAX), _read(form["template_json"], CONFIG_MAX), _read(form["values_json"], VALUES_MAX))
        output, filename = await _document_work("generate", {
            "docx":docx,"config":config,"values":values,"fingerprint":fingerprint})
        ascii_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
        disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
        return Response(output, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": disposition, "Content-Length": str(len(output))})
    finally: heavy.release()

app = api
