"""Conservative container recognition without decoding untrusted media."""
import io
import wave

from ..errors import AppError


def inspect_audio(data: bytes):
    if not data:
        raise AppError("AUDIO_EMPTY", 422)
    extension = None
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE": extension = "wav"
    elif data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"): extension = "mp3"
    elif data[:4] == b"fLaC": extension = "flac"
    elif data[:4] == b"OggS": extension = "ogg"
    elif data[:4] == b"\x1aE\xdf\xa3": extension = "webm"
    elif len(data) >= 12 and data[4:8] == b"ftyp": extension = "m4a"
    if not extension:
        raise AppError("AUDIO_FORMAT_UNSUPPORTED", 415)
    duration = None
    if extension == "wav":
        try:
            with wave.open(io.BytesIO(data), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
        except (wave.Error, EOFError, ZeroDivisionError):
            raise AppError("AUDIO_FORMAT_UNSUPPORTED", 415)
        if duration > 600:
            raise AppError("AUDIO_TOO_LONG", 422)
    return extension, duration
