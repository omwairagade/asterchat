"""Managed MySQL helpers for account registration and daily quota accounting."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from urllib.parse import parse_qs, unquote, urlsplit

import pymysql

DAILY_LIMIT = 100
SCHEMA_VERSION = "001"


def account_key(open_id: str) -> str:
    """Store a stable opaque account key instead of the provider's raw identity."""
    if not isinstance(open_id, str) or not open_id or len(open_id) > 2048:
        raise ValueError("Invalid account identity")
    return hashlib.sha256(open_id.encode("utf-8")).hexdigest()


def connect():
    """Connect using the platform DSN and require its declared TLS verification."""
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL is unavailable")
    parts = urlsplit(dsn)
    if parts.scheme != "mysql" or not parts.hostname or not parts.username or not parts.path.strip("/"):
        raise RuntimeError("DATABASE_URL has an unsupported format")
    options = parse_qs(parts.query)
    ssl_policy = options.get("ssl", [""])[0]
    try:
        tls = json.loads(ssl_policy) if ssl_policy else {}
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DATABASE_URL does not declare a supported TLS policy") from exc
    if not isinstance(tls, dict) or tls.get("rejectUnauthorized") is not True:
        raise RuntimeError("Managed database TLS verification is required")

    ssl_config: dict[str, object] | None = None
    for key in ("ca", "cert", "key", "capath", "cipher"):
        value = tls.get(key)
        if value:
            ssl_config = ssl_config or {}
            ssl_config[key] = value

    return pymysql.connect(
        host=parts.hostname,
        port=parts.port or 3306,
        user=unquote(parts.username),
        password=unquote(parts.password or ""),
        database=unquote(parts.path.lstrip("/")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=8,
        read_timeout=20,
        write_timeout=20,
        ssl=ssl_config,
    )


def verify_schema() -> None:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT version FROM aster_schema_migrations WHERE version = %s",
                (SCHEMA_VERSION,),
            )
            if cursor.fetchone() is None:
                raise RuntimeError("Aster database migration 001 is not applied")
        connection.commit()
    finally:
        connection.close()


def ensure_account(open_id: str) -> str:
    key = account_key(open_id)
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO aster_accounts (account_key) VALUES (%s) "
                "ON DUPLICATE KEY UPDATE account_key = VALUES(account_key)",
                (key,),
            )
        connection.commit()
        return key
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_daily_count(key: str, usage_day: date) -> int:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT messages_used FROM aster_daily_usage "
                "WHERE account_key = %s AND usage_day = %s",
                (key, usage_day),
            )
            row = cursor.fetchone()
        connection.commit()
        return int(row["messages_used"]) if row else 0
    finally:
        connection.close()


def reserve_daily_message(key: str, usage_day: date, limit: int = DAILY_LIMIT) -> tuple[bool, int]:
    """Atomically reserve one user message; concurrent devices cannot exceed the cap."""
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO aster_daily_usage (account_key, usage_day, messages_used) "
                "VALUES (%s, %s, 0) ON DUPLICATE KEY UPDATE account_key = VALUES(account_key)",
                (key, usage_day),
            )
            cursor.execute(
                "UPDATE aster_daily_usage SET messages_used = messages_used + 1 "
                "WHERE account_key = %s AND usage_day = %s AND messages_used < %s",
                (key, usage_day, limit),
            )
            accepted = cursor.rowcount == 1
            cursor.execute(
                "SELECT messages_used FROM aster_daily_usage "
                "WHERE account_key = %s AND usage_day = %s",
                (key, usage_day),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("The daily quota row could not be read")
            used = int(row["messages_used"])
        connection.commit()
        return accepted, used
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
