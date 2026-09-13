"""Fixed-destination, per-request provider relay."""
import asyncio
import json
from dataclasses import dataclass

import httpx

from ..errors import AppError
from ..settings import RESPONSE_MAX, TRANSCRIPT_MAX


@dataclass(frozen=True)
class Provider:
    endpoint: str
    models: frozenset[str]
    formats: frozenset[str]


PROVIDERS = {
    "groq": Provider("https://api.groq.com/openai/v1/audio/transcriptions",
        frozenset({"whisper-large-v3-turbo", "whisper-large-v3"}),
        frozenset({"wav", "mp3", "flac", "ogg", "webm", "m4a", "mp4", "mpeg", "mpga"})),
    "mistral": Provider("https://api.mistral.ai/v1/audio/transcriptions",
        frozenset({"voxtral-mini-2602"}), frozenset({"wav", "mp3", "flac", "ogg", "webm"})),
}


def _retry_after(response):
    try:
        value = int(response.headers.get("retry-after", ""))
        return value if 1 <= value <= 3600 else None
    except ValueError:
        return None


async def _bounded_json(response):
    data = bytearray()
    async for chunk in response.aiter_bytes():
        data.extend(chunk)
        if len(data) > RESPONSE_MAX:
            raise AppError("PROVIDER_RESPONSE_INVALID", 502)
    try:
        return json.loads(bytes(data))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AppError("PROVIDER_RESPONSE_INVALID", 502)


async def relay_transcription(provider_name, model, key, audio, extension, language=None, transport=None):
    provider = PROVIDERS.get(provider_name)
    if provider is None or model not in provider.models:
        raise AppError("MODEL_UNAVAILABLE", 503)
    if extension not in provider.formats:
        raise AppError("AUDIO_FORMAT_UNSUPPORTED", 415)
    fields = {"model": model}
    if language:
        fields["language"] = language
    timeout = httpx.Timeout(connect=10, write=30, read=75, pool=2)
    try:
        async with asyncio.timeout(90):
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False,
                                         transport=transport) as client:
                async with client.stream("POST", provider.endpoint,
                    headers={"Authorization": f"Bearer {key}"}, data=fields,
                    files={"file": (f"audio.{extension}", audio, "application/octet-stream")}) as response:
                    if response.status_code in (401, 403):
                        raise AppError("PROVIDER_KEY_REJECTED", 422)
                    if response.status_code == 402:
                        raise AppError("PROVIDER_PAYMENT_REQUIRED", 402)
                    if response.status_code == 429:
                        raise AppError("PROVIDER_RATE_LIMITED", 429, retryable=True, retry_after=_retry_after(response))
                    if response.status_code in (404, 410, 422):
                        raise AppError("MODEL_UNAVAILABLE", 503)
                    if response.status_code >= 500:
                        raise AppError("PROVIDER_UNAVAILABLE", 502, retryable=True)
                    if not 200 <= response.status_code < 300:
                        raise AppError("PROVIDER_RESPONSE_INVALID", 502)
                    payload = await _bounded_json(response)
    except AppError:
        raise
    except (asyncio.TimeoutError, httpx.TimeoutException):
        raise AppError("PROVIDER_TIMEOUT", 504, retryable=True)
    except httpx.HTTPError:
        raise AppError("PROVIDER_UNAVAILABLE", 502, retryable=True)
    finally:
        key = None
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        raise AppError("PROVIDER_RESPONSE_INVALID", 502)
    if "model" in payload and payload["model"] != model:
        raise AppError("PROVIDER_RESPONSE_INVALID", 502)
    text = payload["text"]
    if not text.strip():
        raise AppError("NO_SPEECH_RECOGNIZED", 422)
    if len(text) > TRANSCRIPT_MAX:
        raise AppError("PROVIDER_RESPONSE_INVALID", 502)
    detected = payload.get("language") if isinstance(payload.get("language"), str) else None
    if detected and (len(detected) > 16 or not detected.replace("-", "").isalpha()):
        detected = None
    return text, detected
