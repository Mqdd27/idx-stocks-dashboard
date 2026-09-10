import argparse
import time
from datetime import date, datetime, timedelta, timezone

from curl_cffi import requests
from sqlalchemy import select

from app.db import SessionLocal
from app.market_calendar import is_trading_day, today_jakarta
from app.models import Company, ForeignFlowDaily

URL = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
SOURCE = "IDX GetStockSummary"
HEADERS = {"accept": "application/json, text/plain, */*", "accept-language": "en-US,en;q=0.9", "referer": "https://www.idx.co.id/"}
MAX_BACKFILL_DAYS = 66


def fetch(day: date):
    response = requests.get(URL, params={"date": day.strftime("%Y%m%d"), "start": 0, "length": 9999}, headers=HEADERS, impersonate="chrome", timeout=30)
    if response.status_code != 200: raise RuntimeError(f"IDX GetStockSummary HTTP {response.status_code}")
    rows = response.json().get("data")
    if not isinstance(rows, list) or not rows: raise RuntimeError("IDX GetStockSummary returned no rows")
    if not {"ForeignBuy", "ForeignSell"} <= set(rows[0]): raise RuntimeError("IDX response lacks explicit ForeignBuy/ForeignSell")
    return rows


def ingest(day: date):
    if not is_trading_day(day): return {"status": "SKIPPED", "reason": "NON_TRADING_DAY", "date": day.isoformat()}
    rows = fetch(day)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        companies = {company.symbol: company.id for company in db.execute(select(Company)).scalars()}
        created = updated = 0
        for raw in rows:
            company_id = companies.get(raw.get("StockCode"))
            buy, sell = raw.get("ForeignBuy"), raw.get("ForeignSell")
            if not company_id or buy is None or sell is None: continue
            row = db.execute(select(ForeignFlowDaily).where(ForeignFlowDaily.company_id == company_id, ForeignFlowDaily.trading_date == day, ForeignFlowDaily.source == SOURCE)).scalar_one_or_none()
            values = {"foreign_buy_volume": int(buy), "foreign_sell_volume": int(sell), "net_foreign_volume": int(buy) - int(sell), "total_traded_volume": int(raw.get("Volume") or 0), "source_timestamp": datetime.fromisoformat(raw["Date"]).replace(tzinfo=timezone.utc) if raw.get("Date") else None, "updated_at": now}
            if row:
                for key, value in values.items(): setattr(row, key, value)
                updated += 1
            else:
                db.add(ForeignFlowDaily(company_id=company_id, trading_date=day, source=SOURCE, **values))
                created += 1
        db.commit()
    return {"status": "OK", "date": day.isoformat(), "created": created, "updated": updated, "source": SOURCE, "data_type": "VOLUME_EOD"}


def backfill(start: date, end: date):
    if end < start or (end - start).days > MAX_BACKFILL_DAYS * 2: raise ValueError(f"Backfill range is bounded to {MAX_BACKFILL_DAYS} calendar days")
    results = []
    day = start
    while day <= end:
        if is_trading_day(day):
            results.append(ingest(day))
            time.sleep(1)
        day += timedelta(days=1)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--from", dest="start", type=date.fromisoformat)
    parser.add_argument("--to", dest="end", type=date.fromisoformat)
    args = parser.parse_args()
    if bool(args.start) != bool(args.end): parser.error("--from and --to must be used together")
    print(backfill(args.start, args.end) if args.start else ingest(args.date or today_jakarta()))
