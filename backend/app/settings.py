"""Non-secret deployment configuration; fixed safety ceilings cannot be raised by visitors."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

AUDIO_MAX = 8_388_608
TRANSCRIPTION_BODY_MAX = 9_437_184
DOCUMENT_BODY_MAX = 3_145_728
DOCX_MAX = 2_097_152
CONFIG_MAX = 131_072
VALUES_MAX = 262_144
RESPONSE_MAX = 1_048_576
TRANSCRIPT_MAX = 100_000


@dataclass(frozen=True)
class Settings:
    production: bool = True
    origins: tuple[str, ...] = ()
    ingress_seconds: float = 90
    provider_seconds: float = 90
    transcription_seconds: float = 180
    document_seconds: float = 120
    restart_on_cleanup_failure: bool = True

    @classmethod
    def from_env(cls):
        production = os.getenv("APP_ENV", "production") != "development"
        origins = tuple(x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip())
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ({"https"} if production else {"http", "https"})
                or not parsed.netloc or parsed.path or parsed.query or parsed.fragment
                or parsed.username or parsed.password or "*" in origin):
                raise RuntimeError("Invalid origin configuration")
        return cls(production=production, origins=origins)
