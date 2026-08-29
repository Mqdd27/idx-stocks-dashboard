import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.recommendation_service import generate_quant, generate_tradingagents_shortlist, update_outcomes
from app.watchlist_service import generate_watchlist, refresh_status
from app.market_calendar import get_market_status

now = datetime.now(ZoneInfo("Asia/Jakarta"))
market = get_market_status(now)
print("OUTCOMES", update_outcomes(now), flush=True)
if not market["is_trading_day"] or not market["is_open"]:
    raise SystemExit(0)
print(f"RECOMMENDATION_WORKER_START date={now.date()} status={market['status']}", flush=True)
if now.hour == 9:
    print("PAPER_GENERAL", generate_quant("GENERAL"), flush=True)
    print("PAPER_BPJS", generate_quant("BPJS"), flush=True)
elif now.hour == 15:
    print("PAPER_BSJP", generate_quant("BSJP"), flush=True)
print("TA_SHORTLIST", generate_tradingagents_shortlist("GENERAL" if now.hour == 9 else "BSJP"), flush=True)
print("WATCHLIST_GENERATE", generate_watchlist(now), flush=True)
print("WATCHLIST_STATUS", refresh_status(now), flush=True)
