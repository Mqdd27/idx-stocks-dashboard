from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.market_calendar import is_trading_day, next_trading_day
from app.recommendation_service import _score, _setup, generate_quant

setup = _setup(100.0, 5.0, 120.0, 90.0)
assert setup is not None
assert setup["stop"] < setup["entry"] < setup["tp1"] <= setup["tp2"]
assert setup["rr"] >= 1.5
score_a = _score({"sma20": 90, "sma50": 85, "rsi14": 58, "macd": {"histogram": 2}}, 2_000_000_000, 1.8, 100, 120, "GENERAL")
score_b = _score({"sma20": 90, "sma50": 85, "rsi14": 58, "macd": {"histogram": 2}}, 2_000_000_000, 1.8, 100, 120, "GENERAL")
assert score_a == score_b
assert not is_trading_day(date(2026, 8, 29))
assert next_trading_day(date(2026, 8, 28)) == date(2026, 8, 31)
weekend = datetime(2026, 8, 29, 12, tzinfo=ZoneInfo("Asia/Jakarta"))
assert generate_quant("BSJP", now=weekend)["status"] == "NO_TRADE"
assert generate_quant("BPJS", now=weekend)["generated"] == 0
print("recommendation safety checks passed")
