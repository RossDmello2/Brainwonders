"""Deliberately categorical operational signals, without request data."""
import logging

logger = logging.getLogger("cls.outcome")


def configure_logging():
    for name in ("uvicorn.access", "httpx", "httpcore", "python_multipart"):
        logging.getLogger(name).disabled = True


def outcome(request_id, route, status, code):
    # Values are generated internally; never pass an exception or a request object.
    logger.info("request_id=%s route=%s status=%s outcome=%s", request_id, route, status, code)
