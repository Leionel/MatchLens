"""Minimal server-side role boundary for editorial actions.

Anonymous viewers may read public match content. Editorial approval requires a
server-configured token; a client-supplied display name is never an identity.
For local production previews an explicit opt-in env flag plus loopback origin
can enable a `local-producer` principal, but public deployments must set a token.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request

Role = Literal["viewer", "analyst", "producer", "admin"]
_PRODUCER_ROLES = {"producer", "admin"}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role

    @property
    def can_edit_content(self) -> bool:
        return self.role in _PRODUCER_ROLES


def _configured_token(role: Role) -> str | None:
    if role == "admin":
        return os.getenv("MATCHLENS_ADMIN_TOKEN") or None
    return os.getenv("MATCHLENS_PRODUCER_TOKEN") or None


def _loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def authenticate(request: Request) -> Principal:
    """Resolve a principal from server-side configuration, never from body text."""
    supplied = request.headers.get("X-MatchLens-Token", "")
    admin = _configured_token("admin")
    producer = _configured_token("producer")
    if supplied and admin and hmac.compare_digest(supplied, admin):
        return Principal("admin", "admin")
    if supplied and producer and hmac.compare_digest(supplied, producer):
        return Principal("producer", "producer")

    if (
        os.getenv("MATCHLENS_ALLOW_LOCAL_PRODUCER", "0") == "1"
        and _loopback(request)
        and request.headers.get("X-MatchLens-Local-Producer") == "1"
    ):
        return Principal("local-producer", "producer")

    # No configured producer boundary means editorial actions are closed, not
    # open to anonymous callers.
    if not admin and not producer:
        raise HTTPException(503, "editorial_identity_not_configured")
    raise HTTPException(403, "editorial_role_required")


def require_content_editor(request: Request) -> Principal:
    principal = authenticate(request)
    if not principal.can_edit_content:
        raise HTTPException(403, "editorial_role_required")
    return principal
