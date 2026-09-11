import json
import os
import sys
import time
import asyncio
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "backend"))
sys.path.insert(0, str(root))

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.market_calendar import is_trading_day
from shared.common import upsert_companies, now_wib, get_logger

logger = get_logger("desktop")


from collector.daily_sync import all_symbols, load_seed, sync_fundamentals, sync_prices


def sync_once() -> dict:
    from collector.news import sync_news
    from scripts.foreign_flow_ingest import ingest_latest_available
    from scripts.broker_activity_ingest import ingest

    symbols = all_symbols()
    asyncio.run(sync_prices(symbols))
    asyncio.run(sync_fundamentals(symbols))
    names = {s: s for s, _ in symbols}
    asyncio.run(sync_news(symbols, names))
    try:
        flow = ingest_latest_available(now_wib().date())
        ingest(flow["date"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("foreign/broker sync skipped: %s", exc)
    return {"symbols": len(symbols), "at": now_wib().isoformat()}


def main() -> None:
    settings = get_settings()
    init_db()
    upsert_companies(load_seed())
    logger.info("desktop bootstrap: schema and seed ready, db=%s", settings.database_url)

    if os.environ.get("DESKTOP_SYNC_ONLY") == "1":
        print(json.dumps(sync_once()))
        return

    if settings.admin_api_token and os.environ.get("DESKTOP_SKIP_SYNC") != "1":
        sync_once()

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("DESKTOP_PORT", "8200")), log_level="info")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        logger.error("desktop bootstrap failed: %s", exc)
        raise