"""Shared helpers for collector and backend."""
import json
import logging
import sys
from datetime import datetime, date, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app import models as db_models  # noqa: E402

TZ = ZoneInfo("Asia/Jakarta")

# IDX trading hours (WIB): pre-open 09:00-09:15, regular 09:15-11:30, 13:30-15:30
PRE_OPEN_START = dtime(9, 0)
PRE_OPEN_END = dtime(9, 15)
MORNING_END = dtime(11, 30)
AFTERNOON_START = dtime(13, 30)
CLOSE_TIME = dtime(15, 30)


def now_wib() -> datetime:
    return datetime.now(TZ)


def is_market_open(now: datetime | None = None) -> bool:
    now = now or now_wib()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (PRE_OPEN_START <= t < MORNING_END) or (AFTERNOON_START <= t <= CLOSE_TIME)


def is_market_hours(now: datetime | None = None) -> bool:
    """True during regular trading sessions (no pre-open)."""
    now = now or now_wib()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (dtime(9, 15) <= t < MORNING_END) or (AFTERNOON_START <= t < CLOSE_TIME)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    return logger


def log_to_db(collector: str, level: str, message: str, details: dict | None = None) -> None:
    try:
        db = SessionLocal()
        db.add(
            db_models.CollectorLog(
                collector=collector, level=level, message=message[:2000], details=details
            )
        )
        db.commit()
        db.close()
    except Exception:
        pass


YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def get_company(symbol: str) -> db_models.Company | None:
    from sqlalchemy import select

    db = SessionLocal()
    try:
        company = db.execute(
            select(db_models.Company).where(db_models.Company.symbol == symbol.upper())
        ).scalar_one_or_none()
        return company
    finally:
        db.close()


def upsert_companies(rows: list[dict]) -> None:
    """rows: symbol, company_name, sector, subsector, listing_date, website, yahoo_symbol."""
    from sqlalchemy import select

    db = SessionLocal()
    try:
        for row in rows:
            symbol = str(row["symbol"]).upper()
            existing = db.execute(
                select(db_models.Company).where(db_models.Company.symbol == symbol)
            ).scalar_one_or_none()
            if existing:
                for key in ("company_name", "sector", "subsector", "listing_date", "website", "yahoo_symbol"):
                    if row.get(key):
                        setattr(existing, key, row[key])
                existing.updated_at = now_wib()
            else:
                db.add(
                    db_models.Company(
                        symbol=symbol,
                        company_name=row.get("company_name") or symbol,
                        sector=row.get("sector"),
                        subsector=row.get("subsector"),
                        listing_date=row.get("listing_date"),
                        website=row.get("website"),
                        yahoo_symbol=row.get("yahoo_symbol") or f"{symbol}.JK",
                    )
                )
        db.commit()
    finally:
        db.close()