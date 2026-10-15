"""Endpoint authentication for the public HTTPS URL.

Two ways to present the same secret token (use whichever your client supports):
  A) Header:       Authorization: Bearer <token>        -> https://host/mcp
  B) Secret path:  https://host/<token>/mcp             (for clients with no header option)

Everything else gets 401. Comparisons are constant-time.
"""
import hmac
import json

from . import config

MIN_TOKEN_LENGTH = 24
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def check_startup_auth() -> None:
    """Refuse unsafe setups before the server starts listening."""
    token = config.AUTH_TOKEN
    if token and len(token) < MIN_TOKEN_LENGTH:
        raise SystemExit(f"MCP_AUTH_TOKEN is too short; use at least {MIN_TOKEN_LENGTH} random characters.")
    if not token and config.HOST not in LOCAL_HOSTS:
        raise SystemExit("Refusing to start: MCP_HOST is not local and MCP_AUTH_TOKEN is empty.")
    if not token:
        print("WARNING: no MCP_AUTH_TOKEN set. Running unauthenticated on localhost only.")


class TokenAuthMiddleware:
    """Pure ASGI middleware, so it also protects the streaming responses."""

    def __init__(self, app, token: str):
        if not token:
            raise ValueError("token must not be empty")
        self.app = app
        self.token = token.encode()

    async def __call__(self, scope, receive, send):
        kind = scope["type"]
        if kind == "lifespan":
            return await self.app(scope, receive, send)
        if kind != "http":
            if kind == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        stripped = self._strip_secret_prefix(scope)
        if stripped is not None:
            return await self.app(stripped, receive, send)
        if self._bearer_ok(scope):
            return await self.app(scope, receive, send)
        await self._deny(send)

    # --- Plan B: /<token>/mcp ---
    def _strip_secret_prefix(self, scope):
        parts = scope.get("path", "").split("/", 2)  # ['', first, rest]
        if len(parts) < 2 or not hmac.compare_digest(parts[1].encode(), self.token):
            return None
        new_path = "/" + (parts[2] if len(parts) > 2 else "")
        new_scope = dict(scope)
        new_scope["path"] = new_path
        new_scope["raw_path"] = new_path.encode()
        return new_scope

    # --- Plan A: Authorization: Bearer <token> ---
    def _bearer_ok(self, scope) -> bool:
        for name, value in scope.get("headers", []):
            if name.lower() == b"authorization":
                scheme, _, credential = value.partition(b" ")
                return scheme.lower() == b"bearer" and hmac.compare_digest(credential.strip(), self.token)
        return False

    @staticmethod
    async def _deny(send) -> None:
        body = json.dumps({"error": "unauthorized"}).encode()
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
