"""Intraday collector - long-running service.

Polls Yahoo 1m chart during IDX trading hours (Asia/Jakarta) every
MARKET_POLL_INTERVAL seconds. Sleeps outside market hours. No requests
to the provider when the market is closed.
"""
import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.common import (  # noqa: E402
    SessionLocal,
    get_logger,
    is_market_hours,
    get_market_status,
    next_market_open,
    log_to_db,
    now_wib,
)
from app import models as db_models  # noqa: E402
from app.config import get_settings  # noqa: E402
from collector import yahoo  # noqa: E402

logger = get_logger("intraday")
settings = get_settings()

_POLL_INTERVAL = max(15, settings.market_poll_interval)
_CONCURRENCY = 8


def tracked_symbols() -> list[tuple[int, str, str]]:
    """(company_id, symbol, yahoo_symbol) for all companies."""
    from sqlalchemy import select

    db = SessionLocal()
    try:
        rows = db.execute(
            select(db_models.Company.id, db_models.Company.symbol, db_models.Company.yahoo_symbol)
        ).all()
        return [(r[0], r[1], r[2]) for r in rows]
    finally:
        db.close()


def store_intraday(company_id: int, rows: list[dict]) -> int:
    from sqlalchemy import select

    db = SessionLocal()
    count = 0
    try:
        for row in rows:
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            existing = db.execute(
                select(db_models.IntradayPrice).where(
                    db_models.IntradayPrice.company_id == company_id,
                    db_models.IntradayPrice.timestamp == ts,
                    db_models.IntradayPrice.source == "yahoo",
                )
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(
                db_models.IntradayPrice(
                    company_id=company_id,
                    timestamp=ts,
                    price=row.get("price"),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    volume=row.get("volume"),
                    source="yahoo",
                )
            )
            count += 1
        db.commit()
        return count
    finally:
        db.close()


async def poll_once(client: httpx.AsyncClient) -> None:
    symbols = tracked_symbols()
    if not symbols:
        return

    async def fetch_one(item: tuple[int, str, str]) -> tuple[str, int]:
        company_id, symbol, yahoo_symbol = item
        try:
            chart = await yahoo.fetch_chart(yahoo_symbol, "1d", "1m", client=client)
            rows = yahoo.chart_to_intraday_rows(chart) if chart else []
            meta = chart.get("meta", {}) if chart else {}
            if not rows:
                chart5 = await yahoo.fetch_chart(yahoo_symbol, "5d", "5m", client=client)
                rows5 = yahoo.chart_to_intraday_rows(chart5) if chart5 else []
                meta = chart5.get("meta", {}) if chart5 else meta
                rows = rows5
            if not rows:
                price = meta.get("regularMarketPrice")
                market_time = meta.get("regularMarketTime")
                if price is None or not market_time:
                    return symbol, 0
                rows = [
                    {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(market_time)) + "Z",
                        "price": price,
                        "open": meta.get("regularMarketDayOpen"),
                        "high": meta.get("regularMarketDayHigh"),
                        "low": meta.get("regularMarketDayLow"),
                        "volume": meta.get("regularMarketVolume") or 0,
                    }
                ]
            # Keep only today's WIB rows
            today_wib = now_wib().date()
            kept = []
            for row in rows:
                ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                if ts.astimezone(settings_timezone()).date() == today_wib:
                    kept.append(row)
            added = store_intraday(company_id, kept)
            return symbol, added
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s intraday failed: %s", symbol, exc)
            return symbol, 0

    sem = asyncio.Semaphore(_CONCURRENCY)

    async def guarded(item):
        async with sem:
            return await fetch_one(item)

    results = await asyncio.gather(*(guarded(item) for item in symbols))
    total = sum(r[1] for r in results)
    logger.info("intraday poll: %d/%d symbols, %d new rows", len(results), len(symbols), total)


def settings_timezone():
    from zoneinfo import ZoneInfo

    return ZoneInfo(settings.timezone)


async def run_forever() -> None:
    logger.info("intraday collector started, interval=%ss", _POLL_INTERVAL)
    log_to_db("intraday", "info", f"started, interval={_POLL_INTERVAL}s")
    while True:
        now = now_wib()
        market = get_market_status(now)
        if is_market_hours(now):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    await poll_once(client)
            except Exception as exc:  # noqa: BLE001
                logger.error("poll cycle failed: %s", exc)
                log_to_db("intraday", "error", f"poll cycle failed: {exc}")
        else:
            next_open = next_market_open(now)
            wait = max(15, (next_open - now).total_seconds())
            logger.info("IDX market %s: %s; sleeping %.0fs until %s", market["status"], market.get("reason") or "outside session", wait, next_open)
            await asyncio.sleep(wait)
            continue
        await asyncio.sleep(_POLL_INTERVAL)


def _next_open(now: datetime) -> datetime:
    candidate = now + timedelta(minutes=1)
    while True:
        if candidate.weekday() >= 5:
            candidate += timedelta(days=1)
            candidate = candidate.replace(hour=9, minute=0, second=0, microsecond=0)
            continue
        t = candidate.time()
        if t.hour < 9:
            candidate = candidate.replace(hour=9, minute=0, second=0, microsecond=0)
            return candidate
        if 11 <= t.hour < 13:
            candidate = candidate.replace(hour=13, minute=30, second=0, microsecond=0)
            return candidate
        if t.hour >= 15:
            candidate += timedelta(days=1)
            candidate = candidate.replace(hour=9, minute=0, second=0, microsecond=0)
            continue
        return candidate


if __name__ == "__main__":
    asyncio.run(run_forever())