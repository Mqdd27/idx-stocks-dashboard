import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from app.market_calendar import get_market_status

TZ = ZoneInfo("Asia/Jakarta")

class CalendarStatusTest(unittest.TestCase):
    def test_next_market_open_is_future_during_session(self):
        now = datetime(2026, 9, 3, 14, 30, tzinfo=TZ)
        status = get_market_status(now)
        self.assertGreater(datetime.fromisoformat(status["next_market_open"]), now)
    def test_weekend_closed(self):
        status = get_market_status(datetime(2026, 9, 5, 10, 0, tzinfo=TZ))
        self.assertFalse(status["is_trading_day"])
        self.assertEqual(status["status"], "WEEKEND")

if __name__ == "__main__": unittest.main()
