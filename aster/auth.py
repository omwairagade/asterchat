"""Manus OAuth helpers and application-session validation."""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit, urlunsplit

import jwt
from jwt import InvalidTokenError

SESSION_COOKIE = "webdev_app_session"
OAUTH_STATE_COOKIE = "aster_oauth_state"
OAUTH_STATE_TTL = 600
SESSION_TTL = 7 * 24 * 60 * 60


def project_id() -> str:
    value = os.environ.get("MANUS_PROJECT_ID", "")
    if not value:
        raise RuntimeError("Manus project identity is unavailable")
    return value


def jwt_secret() -> str:
    value = os.environ.get("MANUS_JWT_SECRET", "")
    if not value:
        raise RuntimeError("Manus session signing secret is unavailable")
    return value


def validate_origin(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Invalid browser origin")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def callback_uri(origin: str) -> str:
    return f"{validate_origin(origin)}/api/auth/callback"


def create_oauth_state(redirect_uri: str) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(32)
    payload = json.dumps(
        {"redirectUri": redirect_uri, "nonce": nonce}, separators=(",", ":")
    ).encode("utf-8")
    state = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    return nonce, state


def parse_oauth_state(state: str) -> dict[str, str] | None:
    try:
        if not state or len(state) > 4096:
            return None
        padding = "=" * (-len(state) % 4)
        payload = json.loads(base64.urlsafe_b64decode(state + padding))
        redirect_uri = payload.get("redirectUri")
        nonce = payload.get("nonce")
        if not isinstance(redirect_uri, str) or not isinstance(nonce, str) or len(nonce) < 32:
            return None
        parts = urlsplit(redirect_uri)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.path != "/api/auth/callback"
            or parts.query
            or parts.fragment
        ):
            return None
        return {"redirectUri": redirect_uri, "nonce": nonce}
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def authorization_url(redirect_uri: str, state: str) -> str:
    portal = os.environ.get("MANUS_OAUTH_PORTAL_URL", "").rstrip("/")
    if not portal:
        raise RuntimeError("Manus sign-in is unavailable")
    query = urlencode(
        {
            "appId": project_id(),
            "redirectUri": redirect_uri,
            "state": state,
            "responseType": "code",
        }
    )
    return f"{portal}/app-auth?{query}"


def issue_session(open_id: str) -> str:
    now = int(time.time())
    payload = {
        "appId": project_id(),
        "openId": open_id,
        "iat": now,
        "exp": now + SESSION_TTL,
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def session_open_id(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            jwt_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "appId", "openId"], "verify_aud": False},
        )
        if payload.get("appId") != project_id():
            return None
        open_id = payload.get("openId")
        return open_id if isinstance(open_id, str) and open_id else None
    except (InvalidTokenError, RuntimeError, TypeError, ValueError):
        return None
