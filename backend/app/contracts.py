"""Typed wire boundaries. Validation input is never reflected to a caller."""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator


class TranscriptionForm(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["groq", "mistral"]
    model: str
    language: str | None = None
    capture_source: Literal["recording", "upload"]
    client_duration_seconds: str | None = None
    duration_unknown_acknowledged: Literal["true", "false"]

    @field_validator("client_duration_seconds")
    @classmethod
    def finite_duration(cls, value):
        if value is not None:
            number = float(value)
            if not math.isfinite(number) or not 0 <= number <= 600:
                raise ValueError("Invalid duration")
        return value


class WarningItem(BaseModel):
    code: Literal["DURATION_UNVERIFIED", "LANGUAGE_MISMATCH", "LANGUAGE_NOT_CONFIRMED", "REVIEW_REQUIRED"]
    message: str


class LanguageResult(BaseModel):
    requested: str | None
    detected: str | None


class AudioResult(BaseModel):
    bytes: int
    duration_seconds: float | None
    duration_source: Literal["server_metadata", "provider_metadata", "unavailable"]


class TranscriptionResult(BaseModel):
    request_id: str
    provider: Literal["groq", "mistral"]
    model: str
    text: str
    language: LanguageResult
    audio: AudioResult
    warnings: list[WarningItem]
