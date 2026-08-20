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
    router_ids = sorted(_router_ids)
    probe_results = await asyncio.gather(
        *(_probe_router_model(m) for m in router_ids if _is_router_model_usable(m))
    )
    probed = dict(zip([m for m in router_ids if _is_router_model_usable(m)], probe_results))
    for m in router_ids:
        heuristic = _is_router_model_usable(m)
        usable = probed.get(m, False) if heuristic else False
        models.append(
            {
                "id": m,
                "name": _pretty_name(m),
                "provider": "9router",
                "local": False,
                "usable": usable,
            }
        )
    return models


def _is_router_model_usable(model_id: str) -> bool:
    """9Router exposes agents that need external accounts (Codex w/ ChatGPT, GitHub,
    etc.). Those fail at request time; mark them so the UI can prefer working models."""
    base = model_id.lower()
    if "codex-spark" in base:
        return False
    if any(x in base for x in ("/opencode", "/mimo", "/claude")):
        return False
    return True


_PROBE_TTL = 300
_probe_cache: dict[str, tuple[float, bool]] = {}


async def _probe_router_model(model_id: str) -> bool:
    now = time.time()
    hit = _probe_cache.get(model_id)
    if hit and now - hit[0] < _PROBE_TTL:
        return hit[1]
    ok = False
    try:
        headers = {"Content-Type": "application/json"}
        if settings.nine_router_api_key:
            headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
        probe_timeout = 180 if model_id.startswith("ollama") else 15
        async with httpx.AsyncClient(timeout=probe_timeout) as client:
            resp = await client.post(
                f"{settings.nine_router_url}/chat/completions",
                headers=headers,
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                    "max_tokens": 1,
                    **({"think": False, "keep_alive": "30m"} if model_id.startswith("ollama") else {}),
                },
            )
            ok = resp.status_code == 200
    except Exception:
        ok = False
    _probe_cache[model_id] = (now, ok)
    return ok


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


_ROUTER_RETRIES = 2


def _retry_delay(attempt: int) -> float:
    return 1.5 * (attempt + 1)


async def _call_router(messages: list[dict], model: str, stream: bool) -> Any:
    headers = {"Content-Type": "application/json"}
    if settings.nine_router_api_key:
        headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
    last_exc: Exception | None = None
    for attempt in range(_ROUTER_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                resp = await client.post(
                    f"{settings.nine_router_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": stream,
                        **({"think": False, "keep_alive": "30m"} if model.startswith("ollama") else {}),
                    },
                )
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < _ROUTER_RETRIES:
                    last_exc = httpx.HTTPStatusError(
                        f"Client error '{resp.status_code}' for url '{resp.url}'", request=resp.request, response=resp
                    )
                    await asyncio.sleep(_retry_delay(attempt))
                    continue
                resp.raise_for_status()
                return resp
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 500, 502, 503, 504) and attempt < _ROUTER_RETRIES:
                last_exc = exc
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
    raise AIError(f"9router request failed after retries: {last_exc}", "9router", model) from last_exc


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
        if is_local or model.startswith("ollama"):
            return _LocalGuard()
        return _noop_guard()

    class _noop_guard:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *exc: Any) -> None:
            return None

    async def _run_stream() -> AsyncIterator[str]:
        nonlocal success, error_msg
        ollama_stream = provider == "ollama" or model.startswith("ollama")
        ollama_model = model.split("/")[-1] if model.startswith("ollama") else model
        try:
            async with await _guard():
                usage: dict = {}
                if ollama_stream:
                    async with httpx.AsyncClient(timeout=900) as client:
                        async with client.stream(
                            "POST",
                            f"{settings.ollama_url}/api/chat",
                            json={
                                "model": ollama_model,
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
                                    usage = chunk
                                    break
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield content
                            _record_router_usage(
                                model,
                                usage.get("prompt_eval_count", 0),
                                usage.get("eval_count", 0),
                            )
                else:
                    headers = {"Content-Type": "application/json"}
                    if settings.nine_router_api_key:
                        headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
                    last_exc: Exception | None = None
                    for attempt in range(_ROUTER_RETRIES + 1):
                        try:
                            async with httpx.AsyncClient(timeout=600) as client:
                                async with client.stream(
                                    "POST",
                                    f"{settings.nine_router_url}/chat/completions",
                                    headers=headers,
                                    json={"model": model, "messages": messages, "stream": True,
                                      **({"think": False, "keep_alive": "30m"} if model.startswith("ollama") else {})},
                                ) as resp:
                                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < _ROUTER_RETRIES:
                                        last_exc = httpx.HTTPStatusError(
                                            f"Client error '{resp.status_code}' for url '{resp.url}'",
                                            request=resp.request,
                                            response=resp,
                                        )
                                        await asyncio.sleep(_retry_delay(attempt))
                                        continue
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
                            break
                        except httpx.HTTPStatusError as exc:
                            if exc.response.status_code in (429, 500, 502, 503, 504) and attempt < _ROUTER_RETRIES:
                                last_exc = exc
                                await asyncio.sleep(_retry_delay(attempt))
                                continue
                            raise
                        except Exception:
                            raise
                    if last_exc is not None:
                        raise AIError(f"9router request failed after retries: {last_exc}", "9router", model) from last_exc
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
            if model.startswith("ollama") or provider == "ollama":
                u = data.get("usage", {})
                _record_router_usage(
                    model,
                    u.get("prompt_tokens", u.get("input_tokens", 0)),
                    u.get("completion_tokens", u.get("output_tokens", 0)),
                )
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


def _record_router_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """9Router's passthrough path never records ollama usage; write it ourselves so
    the 9Router dashboard shows the traffic."""
    try:
        import json as _json
        import sqlite3
        from datetime import datetime, timezone

        base = model.split("/")[-1] if model.startswith("ollama") else model
        if not base:
            return
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        con = sqlite3.connect("/home/mqdd/.9router/db/data.sqlite", timeout=10)
        con.execute(
            "INSERT INTO usageHistory(timestamp, provider, model, connectionId, apiKey, endpoint, promptTokens, completionTokens, cost, status, tokens, meta) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ts,
                "ollama-local",
                base,
                None,
                None,
                f"{settings.nine_router_url}/chat/completions",
                prompt_tokens,
                completion_tokens,
                0.0,
                "ok",
                _json.dumps(
                    {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    }
                ),
                _json.dumps({}),
            ),
        )
        con.commit()
        con.close()
    except Exception:
        pass


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