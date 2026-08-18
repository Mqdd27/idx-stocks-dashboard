"""AI provider abstraction.

Two providers behind one interface:
- cloud: 9Router (OpenAI-compatible, http://127.0.0.1:20128/v1)
- local: Ollama (http://127.0.0.1:11434)

Frontend never sees provider credentials.
Local inference is concurrency-limited (1 active at a time).
"""
import asyncio
import json
import time
from typing import Any, AsyncIterator, Optional

import httpx

from .config import get_settings
from . import models as db_models
from .db import SessionLocal

settings = get_settings()

_LOCAL_LOCK = asyncio.Semaphore(1)
_local_queued = 0

_ollama_ids: set = set()
_router_ids: set = set()
_registry_ts: float = 0.0
_LOCAL_HEURISTIC_PREFIXES = ("qwen", "llama", "mistral", "gemma", "phi", "deepseek-r1", "granite")


class AIError(Exception):
    def __init__(self, message: str, provider: str, model: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model


async def _refresh_registry() -> None:
    global _ollama_ids, _router_ids, _registry_ts
    now = time.time()
    if now - _registry_ts < 30:
        return
    _registry_ts = now
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            if resp.status_code == 200:
                _ollama_ids = {m["name"] for m in resp.json().get("models", [])}
    except Exception:
        pass
    try:
        headers = {}
        if settings.nine_router_api_key:
            headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.nine_router_url}/models", headers=headers)
            if resp.status_code == 200:
                _router_ids = {m["id"] for m in resp.json().get("data", [])}
    except Exception:
        pass


def _model_kind(model_id: str) -> tuple[str, bool]:
    """Return (provider, is_local) without network calls (registry pre-cached)."""
    if model_id in _ollama_ids:
        return "ollama", True
    if model_id in _router_ids:
        return "9router", False
    if model_id.lower().startswith(_LOCAL_HEURISTIC_PREFIXES):
        return "ollama", True
    return "9router", False


async def discover_models() -> list[dict]:
    """Return unified model list: local (Ollama) + cloud (9Router)."""
    await _refresh_registry()
    models: list[dict] = []
    for m in sorted(_ollama_ids):
        models.append({"id": m, "name": _pretty_name(m), "provider": "ollama", "local": True, "usable": True})
    for m in sorted(_router_ids):
        models.append(
            {
                "id": m,
                "name": _pretty_name(m),
                "provider": "9router",
                "local": False,
                "usable": _is_router_model_usable(m),
            }
        )
    return models


def _is_router_model_usable(model_id: str) -> bool:
    """9Router exposes agents that need external accounts (Codex w/ ChatGPT, GitHub,
    etc.). Those fail at request time; mark them so the UI can prefer working models."""
    base = model_id.lower()
    if "codex-spark" in base:
        return False
    if any(x in base for x in ("/opencode", "/mimo", "/claude", "/gemini")):
        return False
    return True


def _pretty_name(model_id: str) -> str:
    base = model_id.split("/")[-1].split(":")[0]
    tag = model_id.split(":")[-1] if ":" in model_id else ""
    return f"{base} ({tag})" if tag and tag != base else base


def get_queue_status() -> dict:
    return {
        "active": _LOCAL_LOCK.locked(),
        "queued": _local_queued,
        "max_concurrency": 1,
    }


class _LocalGuard:
    """Acquires the local lock, tracking queue depth."""

    def __init__(self) -> None:
        self._lock = _LOCAL_LOCK

    async def __aenter__(self) -> None:
        global _local_queued
        if self._lock.locked():
            _local_queued += 1
        await self._lock.acquire()
        if _local_queued > 0:
            _local_queued -= 1

    async def __aexit__(self, *exc: Any) -> None:
        self._lock.release()


async def _call_router(messages: list[dict], model: str, stream: bool) -> Any:
    headers = {"Content-Type": "application/json"}
    if settings.nine_router_api_key:
        headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(
            f"{settings.nine_router_url}/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "stream": stream},
        )
        resp.raise_for_status()
        return resp


async def _call_ollama(messages: list[dict], model: str, stream: bool, max_tokens: int = 1000) -> Any:
    async with httpx.AsyncClient(timeout=900) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": stream,
                "keep_alive": "30m",
                "think": False,
                "options": {"num_predict": max_tokens},
            },
        )
        resp.raise_for_status()
        return resp


async def complete(
    messages: list[dict],
    model: str,
    stream: bool = False,
    request_type: str = "chat",
    symbol: Optional[str] = None,
    max_tokens: int = 1000,
) -> AsyncIterator[str] | str:
    """Unified completion. Yields chunks when stream=True, else returns full text."""
    provider, is_local = _model_kind(model)
    started = time.monotonic()
    success = False
    error_msg: Optional[str] = None

    async def _guard():
        if is_local:
            return _LocalGuard()
        return _noop_guard()

    class _noop_guard:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *exc: Any) -> None:
            return None

    async def _run_stream() -> AsyncIterator[str]:
        nonlocal success, error_msg
        try:
            async with await _guard():
                if provider == "ollama":
                    async with httpx.AsyncClient(timeout=900) as client:
                        async with client.stream(
                            "POST",
                            f"{settings.ollama_url}/api/chat",
                            json={
                                "model": model,
                                "messages": messages,
                                "stream": True,
                                "keep_alive": "30m",
                                "think": False,
                                "options": {"num_predict": max_tokens},
                            },
                        ) as resp:
                            resp.raise_for_status()
                            async for line in resp.aiter_lines():
                                if not line.strip():
                                    continue
                                try:
                                    chunk = json.loads(line)
                                except Exception:
                                    continue
                                if chunk.get("done"):
                                    break
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield content
                else:
                    headers = {"Content-Type": "application/json"}
                    if settings.nine_router_api_key:
                        headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
                    async with httpx.AsyncClient(timeout=600) as client:
                        async with client.stream(
                            "POST",
                            f"{settings.nine_router_url}/chat/completions",
                            headers=headers,
                            json={"model": model, "messages": messages, "stream": True},
                        ) as resp:
                            resp.raise_for_status()
                            async for line in resp.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                except Exception:
                                    continue
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
            success = True
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)[:2000]
            raise AIError(f"{provider} request failed: {exc}", provider, model) from exc
        finally:
            _log_request(model, provider, is_local, request_type, symbol, started, success, error_msg)

    async def _run_full() -> str:
        nonlocal success, error_msg
        try:
            async with await _guard():
                if provider == "ollama":
                    resp = await _call_ollama(messages, model, stream=False, max_tokens=max_tokens)
                    data = resp.json()
                    text = data.get("message", {}).get("content", "")
                else:
                    resp = await _call_router(messages, model, stream=False)
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"]
            success = True
            return text
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)[:2000]
            raise AIError(f"{provider} request failed: {exc}", provider, model) from exc
        finally:
            _log_request(model, provider, is_local, request_type, symbol, started, success, error_msg)

    if stream:
        return _run_stream()
    return await _run_full()


def _log_request(
    model: str,
    provider: str,
    is_local: bool,
    request_type: str,
    symbol: Optional[str],
    started: float,
    success: bool,
    error_msg: Optional[str],
) -> None:
    latency = int((time.monotonic() - started) * 1000)
    try:
        db = SessionLocal()
        db.add(
            db_models.AIRequestLog(
                model=model,
                provider=provider,
                is_local=is_local,
                request_type=request_type,
                symbol=symbol,
                latency_ms=latency,
                success=success,
                error_message=error_msg,
            )
        )
        db.commit()
        db.close()
    except Exception:
        pass