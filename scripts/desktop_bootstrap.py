import asyncio
import json
import os
import sys
from pathlib import Path

import uvicorn
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def load_runtime_env() -> None:
    if len(sys.argv) < 2:
        return
    env_path = Path(sys.argv[1])
    try:
        values = json.loads(env_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid desktop environment file: {exc}") from exc
    if not isinstance(values, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in values.items()
    ):
        raise SystemExit("Invalid desktop environment values")
    os.environ.update(values)


def is_loopback(request: Request) -> bool:
    return request.client is not None and request.client.host in {"127.0.0.1", "::1"}


def sync_once() -> dict:
    from collector.daily_sync import all_symbols, load_seed, sync_fundamentals, sync_prices
    from collector.news import sync_news
    from scripts.foreign_flow_ingest import ingest_latest_available
    from scripts.broker_activity_ingest import ingest
    from shared.common import now_wib, upsert_companies

    upsert_companies(load_seed())
    symbols = all_symbols()
    asyncio.run(sync_prices(symbols))
    asyncio.run(sync_fundamentals(symbols))
    names = {symbol: symbol for symbol, _ in symbols}
    asyncio.run(sync_news(symbols, names))
    try:
        flow = ingest_latest_available(now_wib().date())
        ingest(flow["date"])
    except Exception:
        pass
    return {"symbols": len(symbols), "at": now_wib().isoformat()}


def main() -> None:
    load_runtime_env()
    from app.config import get_settings
    from app.db import init_db
    from app.main import app
    from app.security import valid_symbol

    settings = get_settings()
    static_dir = Path(settings.desktop_static_dir)
    init_db()
    if os.environ.get("DESKTOP_SYNC_ONLY") == "1":
        print(json.dumps(sync_once()))
        return

    if settings.desktop_local_auth:
        @app.middleware("http")
        async def desktop_local_auth(request: Request, call_next):
            if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/") and not is_loopback(request):
                raise HTTPException(403, "Desktop API only accepts local connections")
            return await call_next(request)

    if static_dir.exists():
        @app.get("/stock/{symbol}", include_in_schema=False)
        def desktop_stock_page(symbol: str):
            if not valid_symbol(symbol):
                raise HTTPException(404)
            page = static_dir / "stock" / f"{symbol.upper()}.html"
            if not page.is_file():
                raise HTTPException(404)
            return FileResponse(page)

        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="desktop-static")

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("DESKTOP_PORT", "8200")), log_level="info")


if __name__ == "__main__":
    main()
