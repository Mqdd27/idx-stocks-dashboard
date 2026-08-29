from datetime import date, datetime
from zoneinfo import ZoneInfo
from app.market_calendar import is_trading_day
from app.watchlist_service import _status
from app.recommendation_model import TradeRecommendation

row = TradeRecommendation(entry_low=90, entry_high=100, current_price=95, status="ACTIVE")
assert _status(row, datetime.now(ZoneInfo("Asia/Jakarta"))) == "NEAR_ENTRY"
row.current_price = 120
assert _status(row, datetime.now(ZoneInfo("Asia/Jakarta"))) == "WAIT_ENTRY"
row.status = "EXPIRED"
assert _status(row, datetime.now(ZoneInfo("Asia/Jakarta"))) == "EXPIRED"
assert not is_trading_day(date(2026, 8, 29))
print("AI Watchlist safety checks passed")
