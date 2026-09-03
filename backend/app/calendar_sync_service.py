import json
import os
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from sqlalchemy import desc, select
from .db import SessionLocal
from .models import CollectorLog, MarketHoliday

FALLBACK_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/ID"

def _fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "stocks-dashboard-calendar/1.0"}), timeout=20) as response:
        return json.load(response)

def sync_calendar(year=None):
    year = year or datetime.now().year
    primary = os.environ.get("IDX_CALENDAR_URL", "").strip()
    source = "IDX"
    try:
        if not primary: raise RuntimeError("IDX_CALENDAR_URL not configured")
        payload = _fetch(primary.format(year=year))
        if not isinstance(payload, list) or not payload: raise RuntimeError("IDX calendar returned no holidays")
        url = primary
    except Exception:
        source = "Nager.Date Indonesia public holiday fallback"
        url = FALLBACK_URL.format(year=year)
        payload = _fetch(url)
    if not isinstance(payload, list): raise RuntimeError("calendar payload invalid")
    with SessionLocal() as db:
        count = 0
        for item in payload:
            value = item.get("date")
            if not value: continue
            row = db.execute(select(MarketHoliday).where(MarketHoliday.market == "IDX", MarketHoliday.date == value)).scalar_one_or_none() or MarketHoliday(market="IDX", date=value)
            row.name = item.get("localName") or item.get("name") or "IDX holiday"
            row.holiday_type = "PUBLIC_HOLIDAY"; row.source = source; row.source_url = url; row.is_trading_day = False
            db.add(row); count += 1
        db.add(CollectorLog(collector="market_calendar", level="INFO", message="CALENDAR_SYNC_OK", details={"year": year, "source": source, "count": count}))
        db.commit()
    return {"year": year, "source": source, "count": count}

def calendar_fresh(max_age_hours=72):
    with SessionLocal() as db:
        row = db.execute(select(CollectorLog).where(CollectorLog.collector == "market_calendar", CollectorLog.message == "CALENDAR_SYNC_OK").order_by(desc(CollectorLog.created_at)).limit(1)).scalar_one_or_none()
    return bool(row and row.created_at >= datetime.now(timezone.utc) - timedelta(hours=max_age_hours))
