import json
from datetime import date
from pathlib import Path
from .db import SessionLocal
from .models import MarketHoliday

def import_holidays(path: str):
    db=SessionLocal()
    try:
        for item in json.loads(Path(path).read_text()):
            d=date.fromisoformat(item["date"])
            row=db.query(MarketHoliday).filter_by(market="IDX",date=d).one_or_none() or MarketHoliday(market="IDX",date=d)
            row.name=item["name"]; row.holiday_type=item.get("holiday_type","EXCHANGE_HOLIDAY"); row.source=item.get("source","IDX"); row.source_url=item.get("source_url"); row.is_trading_day=item.get("is_trading_day",False); row.notes=item.get("notes"); db.add(row)
        db.commit()
    finally: db.close()
