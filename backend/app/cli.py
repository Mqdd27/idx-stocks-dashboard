import argparse
from datetime import date
from .db import SessionLocal
from .models import MarketHoliday, MarketCalendarOverride
from .market_calendar import get_market_status

def main():
    p=argparse.ArgumentParser(prog="python -m app.cli")
    sub=p.add_subparsers(dest="command", required=True)
    sub.add_parser("market-status")
    cal=sub.add_parser("market-calendar"); cal.add_argument("--month", required=True)
    hol=sub.add_parser("market-holiday"); hs=hol.add_subparsers(dest="action", required=True)
    add=hs.add_parser("add"); add.add_argument("--date", required=True); add.add_argument("--name", required=True); add.add_argument("--type", required=True); add.add_argument("--source-url", default=None); add.add_argument("--trading-day", action="store_true")
    rem=hs.add_parser("remove"); rem.add_argument("--date", required=True)
    over=sub.add_parser("market-override"); over.add_argument("--date", required=True); over.add_argument("--trading-day", action="store_true"); over.add_argument("--reason", required=True); over.add_argument("--open", dest="open_time", default=None); over.add_argument("--close", dest="close_time", default=None)
    a=p.parse_args()
    if a.command=="market-status":
        s=get_market_status(); print("IDX Market Status"); print(f"Status: {s['status']}\nTrading Day: {s['is_trading_day']}\nReason: {s['reason']}\nNext Open: {s['next_market_open']}"); return
    db=SessionLocal()
    try:
        if a.command=="market-holiday":
            d=date.fromisoformat(a.date)
            if a.action=="remove": db.query(MarketHoliday).filter_by(market="IDX",date=d).delete()
            else:
                row=db.query(MarketHoliday).filter_by(market="IDX",date=d).one_or_none() or MarketHoliday(market="IDX",date=d)
                row.name=a.name; row.holiday_type=a.type; row.source="manual"; row.source_url=a.source_url; row.is_trading_day=a.trading_day
                db.add(row)
            db.commit()
        elif a.command=="market-override":
            d=date.fromisoformat(a.date); row=db.query(MarketCalendarOverride).filter_by(market="IDX",date=d).one_or_none() or MarketCalendarOverride(market="IDX",date=d)
            row.is_trading_day=a.trading_day; row.reason=a.reason; db.add(row); db.commit()
        elif a.command=="market-calendar":
            y,m=map(int,a.month.split("-")); from calendar import monthrange
            from .market_calendar import is_trading_day
            for n in range(1,monthrange(y,m)[1]+1): print(date(y,m,n), "TRADING" if is_trading_day(date(y,m,n)) else "CLOSED")
    finally: db.close()
if __name__=="__main__": main()
