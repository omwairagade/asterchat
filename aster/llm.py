"""Manus AI chat streaming and safe Markdown presentation."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator

import bleach
import httpx
import markdown

SYSTEM_PROMPT = (
    "You are Aster, a thoughtful and practical AI companion. Be warm, clear, and useful. "
    "Help the person reason through questions and find concrete next steps. Do not claim to "
    "remember conversations beyond the messages provided in this request."
)
ALLOWED_TAGS = {
    "a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "hr",
    "li", "ol", "p", "pre", "strong", "ul",
}


def event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def render_markdown(text: str) -> str:
    rendered = markdown.markdown(text, extensions=[])
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes={"a": ["href", "title"]},
        protocols=["http", "https", "mailto"],
        strip=True,
    )


async def stream_chat(messages: list[dict[str, str]], used: int, reset_at: str) -> AsyncIterator[str]:
    api_url = os.environ.get("MANUS_API_URL", "").rstrip("/")
    api_key = os.environ.get("MANUS_API_KEY", "")
    if not api_url or not api_key:
        yield event("error", {"message": "Aster's reply service is not configured."})
        return

    request_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    payload = {
        "messages": request_messages,
        "stream": True,
        "max_tokens": 1000,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    collected: list[str] = []
    yield event(
        "usage",
        {"used": used, "remaining": max(0, 100 - used), "limit": 100, "resetAt": reset_at},
    )

    try:
        timeout = httpx.Timeout(connect=15.0, read=90.0, write=20.0, pool=15.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream(
                "POST", f"{api_url}/v1/chat/completions", json=payload, headers=headers
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    yield event(
                        "error",
                        {"message": "Aster could not get a reply right now. This submitted message used one daily message."},
                    )
                    return
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        if raw == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("error"):
                        yield event(
                            "error",
                            {"message": "Aster could not complete that reply. This submitted message used one daily message."},
                        )
                        return
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if isinstance(delta, str) and delta:
                        collected.append(delta)
                        yield event("delta", {"text": delta})
    except asyncio.CancelledError:
        raise
    except (httpx.TimeoutException, httpx.RequestError):
        yield event(
            "error",
            {"message": "Aster's reply service timed out. This submitted message used one daily message."},
        )
        return
    except Exception:
        yield event(
            "error",
            {"message": "Aster could not complete that reply. This submitted message used one daily message."},
        )
        return

    answer = "".join(collected).strip()
    if not answer:
        yield event("error", {"message": "Aster returned an empty reply. Please try again."})
        return
    yield event("done", {"html": render_markdown(answer)})
