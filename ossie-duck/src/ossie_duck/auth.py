"""API-key authentication shared by the REST API and the MCP HTTP transport.

A pure-ASGI middleware, so it works in front of FastAPI and Starlette apps alike.
Clients send the key as ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``.
Keys are compared in constant time. Keys are never accepted in the query string,
because URLs end up in logs and browser history.

With no keys configured the middleware lets everything through; the CLI only allows
that on a loopback address.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Iterable, Sequence

MIN_KEY_LENGTH = 16
ENV_VAR = "OSSIE_DUCK_API_KEYS"


def parse_keys(value: str | None) -> list[str]:
    """Split a comma-separated list of keys, refusing short ones."""
    keys = [k.strip() for k in (value or "").split(",") if k.strip()]
    short = [k for k in keys if len(k) < MIN_KEY_LENGTH]
    if short:
        raise ValueError(
            f"API keys must be at least {MIN_KEY_LENGTH} characters; "
            f"generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    return keys


def keys_from_env(environ: dict[str, str] | None = None) -> list[str]:
    return parse_keys((environ if environ is not None else os.environ).get(ENV_VAR))


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "::1", "localhost")


def _presented_key(scope: dict) -> str:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    auth = headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return headers.get("x-api-key", "").strip()


class ApiKeyMiddleware:
    def __init__(self, app, keys: Sequence[str], exempt_paths: Iterable[str] = ("/health",)):
        self.app = app
        self.keys = [k.encode() for k in keys]
        self.exempt = frozenset(exempt_paths)

    def _valid(self, presented: str) -> bool:
        candidate = presented.encode()
        ok = False
        for key in self.keys:  # check every key so timing does not reveal which one matched
            ok |= hmac.compare_digest(candidate, key)
        return ok

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan" or not self.keys:
            return await self.app(scope, receive, send)
        if scope["type"] == "http" and scope.get("path") in self.exempt:
            return await self.app(scope, receive, send)
        if scope["type"] == "http" and self._valid(_presented_key(scope)):
            return await self.app(scope, receive, send)

        if scope["type"] == "http":
            body = json.dumps({"error": "missing or invalid API key"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"www-authenticate", b'Bearer realm="ossie-duck"'),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        else:  # websocket or anything else: refuse
            await send({"type": "websocket.close", "code": 1008})
