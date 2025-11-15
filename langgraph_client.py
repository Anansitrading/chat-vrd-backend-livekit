import asyncio
import json
import os
from typing import Any

import httpx
from loguru import logger


LANGGRAPH_URL = os.getenv(
    "LANGGRAPH_URL",
    "https://mvp20-production.up.railway.app/agents/execute/stream",
)


async def _stream_langgraph_response(client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
    parts: list[str] = []

    async with client.stream(
        "POST",
        LANGGRAPH_URL,
        json=payload,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()

        async for line in resp.aiter_lines():
            if not line:
                continue
            if line.startswith(":"):
                continue

            if line.startswith("data: "):
                data_str = line[6:]
            else:
                data_str = line

            token: str | None = None
            try:
                event = json.loads(data_str)
                token = (
                    event.get("token")
                    or event.get("content")
                    or event.get("text")
                    or event.get("delta")
                )
            except Exception:
                token = data_str

            if token:
                parts.append(str(token))

    return "".join(parts)


async def call_langgraph(
    message: str,
    session_id: str,
    language: str,
    input_type: str,
    *,
    max_retries: int = 3,
    timeout: float = 20.0,
) -> str:
    payload: dict[str, Any] = {
        "message": message,
        "thread_id": session_id,
        "user_context": {
            "input_type": input_type,
            "language": language,
            "source": "livekit-deepgram",
        },
    }

    attempt = 0
    last_error: Exception | None = None

    while attempt < max_retries:
        attempt += 1
        try:
            logger.info(
                "Calling LangGraph backend",
                extra={
                    "thread_id": session_id,
                    "language": language,
                    "input_type": input_type,
                    "attempt": attempt,
                },
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await _stream_langgraph_response(client, payload)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_error = exc
            logger.warning(
                "LangGraph call failed",
                extra={
                    "error": str(exc),
                    "attempt": attempt,
                },
            )
            await asyncio.sleep(2 * attempt)

    logger.error("LangGraph call failed after retries", extra={"error": str(last_error) if last_error else None})
    raise RuntimeError("Failed to fetch LangGraph response from backend")
