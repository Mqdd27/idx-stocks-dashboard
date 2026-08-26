"""Safe self-check for AI Auto Trade gates. Does not call an LLM or create a trade."""
from datetime import date

from sqlalchemy import select

from app.ai_auto_trade import _open_paper_trade, get_config, select_candidates
from app.db import SessionLocal
from app.market_calendar import is_trading_day
from app.models import PaperTrade


with SessionLocal() as db:
    config = get_config(db)
    candidates = select_candidates(db, min(3, config.max_candidates))
    assert len(candidates) <= 3
    assert all(candidate["action"] == "buy" for candidate in candidates)

    open_trade = db.execute(select(PaperTrade).where(PaperTrade.status == "open").limit(1)).scalar_one_or_none()
    symbol = open_trade.symbol if open_trade else "BBCA"
    opened, reason = _open_paper_trade(db, 0, symbol, {"action": "NO_TRADE", "decision": "Market Weight"})
    assert not opened and reason == "AI_NO_TRADE"

assert not is_trading_day(date(2026, 8, 29))
print("AI Auto Trade safety checks passed")
