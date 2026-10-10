"""Aster web application: Manus OAuth, account quotas, AI streaming, and static pages."""

from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from aster import auth, db, llm

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
DAILY_LIMIT = db.DAILY_LIMIT
MAX_BODY_BYTES = 128 * 1024
MAX_HISTORY_MESSAGES = 24
MAX_MESSAGE_CHARS = 4000
MAX_TOTAL_CHARS = 16000
PUBLIC_APP_ORIGINS = frozenset(
    {
        "https://asterchat-wfynpmap.manus.space",
        "https://8328-im6byf23rn4o8zixely20-ce0d2e45.sg2.manus.computer",
    }
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_environment()
    await run_in_threadpool(db.verify_schema)
    yield


app = FastAPI(
    title="Aster",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    telemetry={"auto_configure": False},
    lifespan=lifespan,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def usage_day() -> date:
    return utc_now().date()


def reset_time(day: date | None = None) -> str:
    next_day = (day or usage_day()) + timedelta(days=1)
    reset = datetime.combine(next_day, time.min, tzinfo=timezone.utc)
    return reset.isoformat().replace("+00:00", "Z")


def cookie_options(secure: bool, path: str = "/") -> dict:
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "none" if secure else "lax",
        "path": path,
    }


def validate_runtime_environment() -> None:
    required = {
        "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
        "MANUS_PROJECT_ID": os.environ.get("MANUS_PROJECT_ID", ""),
        "MANUS_JWT_SECRET": os.environ.get("MANUS_JWT_SECRET", ""),
        "MANUS_OAUTH_PORTAL_URL": os.environ.get("MANUS_OAUTH_PORTAL_URL", ""),
        "MANUS_OAUTH_API_URL": os.environ.get("MANUS_OAUTH_API_URL", ""),
        "MANUS_API_URL": os.environ.get("MANUS_API_URL", ""),
        "MANUS_API_KEY": os.environ.get("MANUS_API_KEY", ""),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


def require_browser_origin(request: Request) -> str:
    origin = request.headers.get("origin", "")
    try:
        normalized = auth.validate_origin(origin)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="A same-site browser request is required") from exc
    if normalized != origin:
        raise HTTPException(status_code=403, detail="Invalid request origin")
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-site requests are not allowed")
    referer = request.headers.get("referer")
    if referer:
        parts = urlsplit(referer)
        referer_origin = f"{parts.scheme}://{parts.netloc}"
        if not hmac.compare_digest(referer_origin, origin):
            raise HTTPException(status_code=403, detail="Invalid request origin")
    return origin


def public_callback_origin(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="Invalid application origin")
    try:
        origin = auth.validate_origin(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid application origin") from exc
    parts = urlsplit(origin)
    local_http = parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if origin != value or (origin not in PUBLIC_APP_ORIGINS and not local_http):
        raise HTTPException(status_code=400, detail="This Aster origin is not enabled for sign-in")
    return origin


async def read_json(request: Request) -> dict:
    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        raise HTTPException(status_code=415, detail="Expected a JSON request")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="The request is too large")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Invalid request")
    return value


def current_open_id(request: Request) -> str | None:
    return auth.session_open_id(request.cookies.get(auth.SESSION_COOKIE))


def private_json(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/api/healthz")
async def healthz():
    try:
        await run_in_threadpool(db.verify_schema)
    except Exception:
        raise HTTPException(status_code=503, detail="Application data service is not ready")
    return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})


@app.get("/api/auth/session")
async def auth_session(request: Request):
    open_id = current_open_id(request)
    if not open_id:
        return private_json({"authenticated": False, "dailyLimit": DAILY_LIMIT})
    try:
        day = usage_day()
        key = await run_in_threadpool(db.ensure_account, open_id)
        used = await run_in_threadpool(db.get_daily_count, key, day)
    except Exception:
        return private_json({"authenticated": False, "error": "Account service is temporarily unavailable."}, 503)
    return private_json(
        {
            "authenticated": True,
            "provider": "Manus",
            "dailyLimit": DAILY_LIMIT,
            "used": used,
            "remaining": max(0, DAILY_LIMIT - used),
            "resetAt": reset_time(day),
        }
    )


@app.post("/api/auth/start")
async def auth_start(request: Request):
    require_browser_origin(request)
    body = await read_json(request)
    # Preview rebases Origin/Host; accept only the browser-reported Aster origin allowlist.
    origin = public_callback_origin(body.get("origin"))
    redirect_uri = auth.callback_uri(origin)
    nonce, state = auth.create_oauth_state(redirect_uri)
    try:
        url = auth.authorization_url(redirect_uri, state)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Manus sign-in is unavailable") from exc
    secure = urlsplit(origin).scheme == "https"
    response = private_json({"authorizationUrl": url})
    response.set_cookie(
        auth.OAUTH_STATE_COOKIE,
        nonce,
        max_age=auth.OAUTH_STATE_TTL,
        **cookie_options(secure, "/api/auth"),
    )
    return response


@app.get("/api/auth/callback")
async def auth_callback(request: Request):
    state = auth.parse_oauth_state(request.query_params.get("state", ""))
    state_cookie = request.cookies.get(auth.OAUTH_STATE_COOKIE, "")
    if not state or not state_cookie or not hmac.compare_digest(state["nonce"], state_cookie):
        raise HTTPException(status_code=400, detail="The sign-in request expired. Please try again.")
    redirect_uri = state["redirectUri"]
    origin = f"{urlsplit(redirect_uri).scheme}://{urlsplit(redirect_uri).netloc}"
    if redirect_uri != auth.callback_uri(origin):
        raise HTTPException(status_code=400, detail="Invalid sign-in callback")

    code = request.query_params.get("code", "")
    if not code or len(code) > 4096 or request.query_params.get("error"):
        response = RedirectResponse(url="/?auth=failed", status_code=303)
        response.delete_cookie(
            auth.OAUTH_STATE_COOKIE,
            **cookie_options(urlsplit(origin).scheme == "https", "/api/auth"),
        )
        return response

    api_base = os.environ.get("MANUS_OAUTH_API_URL", "").rstrip("/")
    project_id = os.environ.get("MANUS_PROJECT_ID", "")
    if not api_base or not project_id:
        raise HTTPException(status_code=503, detail="Manus sign-in is not configured")
    try:
        timeout = httpx.Timeout(20.0, connect=8.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            exchange = await client.post(
                f"{api_base}/webdev.v1.WebDevAuthPublicService/ExchangeToken",
                json={
                    "clientId": project_id,
                    "grantType": "authorization_code",
                    "code": code,
                    "redirectUri": redirect_uri,
                },
            )
            exchange.raise_for_status()
            access_token = exchange.json().get("accessToken")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("The sign-in exchange did not return an access token")
            identity_response = await client.post(
                f"{api_base}/webdev.v1.WebDevAuthPublicService/GetUserInfo",
                json={"accessToken": access_token},
            )
            identity_response.raise_for_status()
            open_id = identity_response.json().get("openId")
            if not isinstance(open_id, str) or not open_id:
                raise ValueError("The sign-in service did not return an account identity")
        await run_in_threadpool(db.ensure_account, open_id)
        session_token = auth.issue_session(open_id)
    except Exception:
        response = RedirectResponse(url="/?auth=failed", status_code=303)
        response.delete_cookie(
            auth.OAUTH_STATE_COOKIE,
            **cookie_options(urlsplit(origin).scheme == "https", "/api/auth"),
        )
        return response

    secure = urlsplit(origin).scheme == "https"
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        auth.SESSION_COOKIE,
        session_token,
        max_age=auth.SESSION_TTL,
        **cookie_options(secure),
    )
    response.delete_cookie(
        auth.OAUTH_STATE_COOKIE,
        **cookie_options(secure, "/api/auth"),
    )
    return response


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    require_browser_origin(request)
    body = await read_json(request)
    origin = public_callback_origin(body.get("origin"))
    secure = urlsplit(origin).scheme == "https"
    response = private_json({"ok": True})
    response.delete_cookie(auth.SESSION_COOKIE, **cookie_options(secure))
    return response


@app.get("/api/usage")
async def usage(request: Request):
    open_id = current_open_id(request)
    if not open_id:
        raise HTTPException(status_code=401, detail="Sign in to see your daily usage")
    try:
        day = usage_day()
        key = await run_in_threadpool(db.ensure_account, open_id)
        used = await run_in_threadpool(db.get_daily_count, key, day)
    except Exception:
        raise HTTPException(status_code=503, detail="The usage service is temporarily unavailable")
    return private_json(
        {
            "used": used,
            "remaining": max(0, DAILY_LIMIT - used),
            "dailyLimit": DAILY_LIMIT,
            "resetAt": reset_time(day),
        }
    )


def validate_messages(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value or len(value) > MAX_HISTORY_MESSAGES:
        raise HTTPException(status_code=400, detail="Send a shorter conversation")
    messages: list[dict[str, str]] = []
    total = 0
    for item in value:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            raise HTTPException(status_code=400, detail="The conversation format is invalid")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            raise HTTPException(status_code=400, detail="Each message must contain 1–4,000 characters")
        total += len(content)
        messages.append({"role": item["role"], "content": content.strip()})
    if total > MAX_TOTAL_CHARS or messages[0]["role"] != "user" or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="The conversation is too long or incomplete")
    return messages


@app.post("/api/chat")
async def chat(request: Request):
    require_browser_origin(request)
    open_id = current_open_id(request)
    if not open_id:
        raise HTTPException(status_code=401, detail="Sign in before sending a message")
    body = await read_json(request)
    messages = validate_messages(body.get("messages"))
    try:
        day = usage_day()
        key = await run_in_threadpool(db.ensure_account, open_id)
        accepted, used = await run_in_threadpool(
            db.reserve_daily_message, key, day, DAILY_LIMIT
        )
    except Exception:
        raise HTTPException(status_code=503, detail="The daily limit service is temporarily unavailable")
    if not accepted:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "You've reached your 100-message limit for today. Your allowance resets at 00:00 UTC.",
                "used": used,
                "remaining": 0,
                "dailyLimit": DAILY_LIMIT,
                "resetAt": reset_time(day),
            },
        )
    return StreamingResponse(
        llm.stream_chat(messages, used, reset_time(day)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )


app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
