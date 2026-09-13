"""Vercel ASGI entrypoint for the Cloud Legal Stenographer API."""

from backend.app.main import app as _app


async def app(scope, receive, send):
    """Remove Vercel's internal /api prefix before FastAPI route matching."""
    if scope.get("type") == "http" and scope.get("path", "").startswith("/api"):
        scope = dict(scope)
        scope["path"] = scope["path"][4:] or "/"
        if scope.get("raw_path"):
            scope["raw_path"] = scope["raw_path"][4:] or b"/"
    await _app(scope, receive, send)
