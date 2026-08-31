import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.recommendation_service import generate_quant, generate_tradingagents_shortlist, update_outcomes
from app.watchlist_service import generate_watchlist, refresh_status
from app.market_calendar import get_market_status
from app.db import SessionLocal
from app.recommendation_model import TradeRecommendation
from scripts.telegram_recommendation import send_report
from sqlalchemy import select, desc


def notify_telegram(strategy, method):
    with SessionLocal() as db:
        rows = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == now.date(), TradeRecommendation.strategy == strategy, TradeRecommendation.method == method, TradeRecommendation.action == "BUY").order_by(desc(TradeRecommendation.score)).limit(10)).scalars().all()
    if not rows:
        return
    lines = [f"{strategy} {method} · {now.strftime('%d %b %Y %H:%M WIB')}"]
    for row in rows:
        lines.append(f"{row.symbol} | Entry {round(row.entry_low or 0)}-{round(row.entry_high or 0)} | TP {round(row.tp1 or 0)} | SL {round(row.stop_loss or 0)} | Score {row.score or '-'}")
    subprocess.run(["/home/mqdd/.local/bin/hermes", "send", "--to", "telegram", "\n".join(lines)], check=False, timeout=30)


now = datetime.now(ZoneInfo("Asia/Jakarta"))
market = get_market_status(now)
print("OUTCOMES", update_outcomes(now), flush=True)
print(f"RECOMMENDATION_WORKER_START date={now.date()} status={market['status']}", flush=True)
if now.hour == 22:
    print("PAPER_BPJS_PREVIEW", generate_quant("BPJS", cycle="night-preview", preview=True), flush=True)
    print("TA_BPJS", generate_tradingagents_shortlist("BPJS", cycle="night-preview", now=now), flush=True)
    print("WATCHLIST_GENERATE", generate_watchlist(now), flush=True)
    print("WATCHLIST_STATUS", refresh_status(now), flush=True)
    raise SystemExit(0)
if not market["is_trading_day"] or not market["is_open"]:
    raise SystemExit(0)
if now.hour == 9:
    print("PAPER_GENERAL", generate_quant("GENERAL"), flush=True)
    print("PAPER_BPJS", generate_quant("BPJS"), flush=True)
elif now.hour == 15:
    print("PAPER_BSJP", generate_quant("BSJP"), flush=True)
print("TA_SHORTLIST", generate_tradingagents_shortlist("GENERAL" if now.hour == 9 else "BSJP"), flush=True)
if now.hour == 15:
    send_report("BSJP")
print("WATCHLIST_GENERATE", generate_watchlist(now), flush=True)
print("WATCHLIST_STATUS", refresh_status(now), flush=True)
