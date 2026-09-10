import argparse
from datetime import date, datetime, timezone

from curl_cffi import requests
from sqlalchemy import select

from app.db import SessionLocal
from app.market_calendar import is_trading_day, today_jakarta
from app.models import BrokerActivityDaily

URL = "https://www.idx.co.id/primary/TradingSummary/GetBrokerSummary"
SOURCE = "IDX GetBrokerSummary"
HEADERS = {"accept": "application/json, text/plain, */*", "accept-language": "en-US,en;q=0.9", "referer": "https://www.idx.co.id/"}


def ingest(day: date):
    if not is_trading_day(day): return {"status": "SKIPPED", "reason": "NON_TRADING_DAY", "date": day.isoformat()}
    response = requests.get(URL, params={"date": day.strftime("%Y%m%d"), "start": 0, "length": 9999}, headers=HEADERS, impersonate="chrome", timeout=30)
    if response.status_code != 200: raise RuntimeError(f"IDX GetBrokerSummary HTTP {response.status_code}")
    rows = response.json().get("data")
    if not isinstance(rows, list) or not rows: raise RuntimeError("IDX GetBrokerSummary returned no rows")
    if not {"IDFirm", "FirmName", "Volume", "Value"} <= set(rows[0]): raise RuntimeError("IDX response lacks broker activity fields")
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        created = updated = 0
        for raw in rows:
            code = raw["IDFirm"]
            row = db.execute(select(BrokerActivityDaily).where(BrokerActivityDaily.broker_code == code, BrokerActivityDaily.trading_date == day, BrokerActivityDaily.source == SOURCE)).scalar_one_or_none()
            values = {"broker_name": raw.get("FirmName"), "volume": int(raw.get("Volume") or 0), "value": raw.get("Value"), "frequency": int(raw.get("Frequency") or 0), "source_timestamp": datetime.fromisoformat(raw["Date"]).replace(tzinfo=timezone.utc) if raw.get("Date") else None, "updated_at": now}
            if row:
                for key, value in values.items(): setattr(row, key, value)
                updated += 1
            else:
                db.add(BrokerActivityDaily(trading_date=day, broker_code=code, source=SOURCE, **values))
                created += 1
        db.commit()
    return {"status": "OK", "date": day.isoformat(), "created": created, "updated": updated, "source": SOURCE, "scope": "MARKET_WIDE_EOD"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=today_jakarta())
    print(ingest(parser.parse_args().date))
