"""Request envelope and response policy enforced before route parsing."""
import asyncio
import uuid

from starlette.responses import JSONResponse

from .errors import MESSAGES
from .settings import DOCUMENT_BODY_MAX, TRANSCRIPTION_BODY_MAX


class RequestPolicyMiddleware:
    def __init__(self, app, origins):
        self.app, self.origins = app, frozenset(origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        raw_headers = scope.get("headers", [])
        if len(raw_headers) > 64 or sum(len(name) + len(value) for name, value in raw_headers) > 16_384:
            return await self._error(scope, receive, send, 400, "REQUEST_INVALID", request_id)
        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in raw_headers}
        origin = headers.get("origin")
        if method == "OPTIONS" and path.startswith("/v1/"):
            if origin not in self.origins:
                return await self._error(scope, receive, send, 403, "ORIGIN_NOT_ALLOWED", request_id)
            response = JSONResponse({}, status_code=204, headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Provider-Key",
                "Access-Control-Max-Age": "600", "Vary": "Origin",
                "Cache-Control": "no-store", "X-Request-Id": request_id})
            return await response(scope, receive, send)
        if method == "POST" and path.startswith("/v1/") and origin not in self.origins:
            return await self._error(scope, receive, send, 403, "ORIGIN_NOT_ALLOWED", request_id)
        cap = TRANSCRIPTION_BODY_MAX if path == "/v1/transcriptions" else DOCUMENT_BODY_MAX if path.startswith("/v1/templates") or path.startswith("/v1/documents") else None
        length = headers.get("content-length")
        if cap and length and length.isdigit() and int(length) > cap:
            return await self._error(scope, receive, send, 413, "INPUT_TOO_LARGE", request_id)
        received = 0
        async def bounded_receive():
            nonlocal received
            message = await asyncio.wait_for(receive(), timeout=90)
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if cap and received > cap:
                    raise BodyTooLarge
            return message
        async def policy_send(message):
            if message["type"] == "http.response.start":
                current = list(message.get("headers", []))
                current.extend([(b"cache-control", b"no-store"), (b"pragma", b"no-cache"),
                    (b"x-request-id", request_id.encode()), (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer")])
                if origin in self.origins:
                    current.extend([(b"access-control-allow-origin", origin.encode()), (b"vary", b"Origin"),
                        (b"access-control-expose-headers", b"Content-Disposition, X-Request-Id, Retry-After")])
                message["headers"] = current
            await send(message)
        try:
            await self.app(scope, bounded_receive, policy_send)
        except BodyTooLarge:
            await self._error(scope, receive, send, 413, "INPUT_TOO_LARGE", request_id)
        except asyncio.TimeoutError:
            await self._error(scope, receive, send, 408, "REQUEST_TIMEOUT", request_id)

    async def _error(self, scope, receive, send, status, code, request_id):
        response = JSONResponse({"error": {"code": code, "message": MESSAGES[code], "retryable": False,
            "request_id": request_id, "details": [], "retry_after_seconds": None}}, status_code=status,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache", "X-Request-Id": request_id})
        await response(scope, receive, send)


class BodyTooLarge(Exception): pass
