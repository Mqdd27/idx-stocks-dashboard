import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from app.performance_service import _metrics, period_bounds
from app.market_calendar import next_trading_day, is_trading_day
TZ = ZoneInfo("Asia/Jakarta")

class BSJPCrossDayTest(unittest.TestCase):
    def row(self, strategy="BSJP", method="PAPER_TRADE", entry_day=date(2026, 9, 4), exit_day=date(2026, 9, 5), value=2.5, status="TP2_HIT", entered=True):
        return SimpleNamespace(strategy=strategy, method=method, trading_date=entry_day, status=status, outcome={"entry_triggered": entered, "return_pct": value, "exit_date": exit_day.isoformat()})
    def test_bsjp_counted_on_entry_date_only(self):
        row = self.row()
        res = _metrics([row], "BSJP", "PAPER_TRADE", "daily", date(2026, 9, 4), date(2026, 9, 4))
        self.assertEqual(res["trades"], 1)
        res = _metrics([row], "BSJP", "PAPER_TRADE", "daily", date(2026, 9, 5), date(2026, 9, 5))
        self.assertEqual(res["trades"], 0)
    def test_bsjp_weekly_includes_entry_week(self):
        row = self.row(entry_day=date(2026, 9, 4), exit_day=date(2026, 9, 7))
        res = _metrics([row], "BSJP", "PAPER_TRADE", "weekly", date(2026, 8, 31), date(2026, 9, 6))
        self.assertEqual(res["trades"], 1)
    def test_bsjp_holiday_weekend_handled(self):
        row = self.row(entry_day=date(2026, 9, 5), exit_day=date(2026, 9, 8))
        res = _metrics([row], "BSJP", "PAPER_TRADE", "daily", date(2026, 9, 5), date(2026, 9, 5))
        self.assertEqual(res["trades"], 1)
        res = _metrics([row], "BSJP", "PAPER_TRADE", "daily", date(2026, 9, 8), date(2026, 9, 8))
        self.assertEqual(res["trades"], 0)

class BPJSOvernightAnomalyTest(unittest.TestCase):
    def row(self, entry_day=date(2026, 9, 4), exit_day=date(2026, 9, 5), value=1.2, status="TP1_HIT", entered=True):
        return SimpleNamespace(strategy="BPJS", method="PAPER_TRADE", trading_date=entry_day, status=status, outcome={"entry_triggered": entered, "return_pct": value, "exit_date": exit_day.isoformat()})
    def test_bpjs_same_day_not_anomaly(self):
        row = self.row(exit_day=date(2026, 9, 4))
        res = _metrics([row], "BPJS", "PAPER_TRADE", "daily", date(2026, 9, 4), date(2026, 9, 4))
        self.assertEqual(res["trades"], 1)
        self.assertEqual(res.get("anomalies", 0), 0)
    def test_bpjs_overnight_anomaly_excluded(self):
        row = self.row(exit_day=date(2026, 9, 5))
        res = _metrics([row], "BPJS", "PAPER_TRADE", "daily", date(2026, 9, 4), date(2026, 9, 4))
        self.assertEqual(res["trades"], 0)
        self.assertEqual(res.get("anomalies", 0), 1)
    def test_bpjs_anomaly_not_in_realized_metrics(self):
        normal = self.row(exit_day=date(2026, 9, 4), value=3.0, status="TP2_HIT")
        anomaly = self.row(exit_day=date(2026, 9, 5), value=-5.0, status="SL_HIT")
        res = _metrics([normal, anomaly], "BPJS", "PAPER_TRADE", "daily", date(2026, 9, 4), date(2026, 9, 4))
        self.assertEqual(res["trades"], 1)
        self.assertEqual(res["winning_trades"], 1)
        self.assertEqual(res["losing_trades"], 0)
        self.assertEqual(res["anomalies"], 1)
    def test_bpjs_anomaly_excluded_from_weekly(self):
        anomaly = self.row(entry_day=date(2026, 9, 4), exit_day=date(2026, 9, 5))
        res = _metrics([anomaly], "BPJS", "PAPER_TRADE", "weekly", date(2026, 8, 31), date(2026, 9, 6))
        self.assertEqual(res["trades"], 0)
        self.assertEqual(res.get("anomalies", 0), 1)

class MarketCalendarTest(unittest.TestCase):
    def test_next_trading_day_friday_to_monday(self):
        fri = date(2026, 9, 4)
        nxt = next_trading_day(fri)
        self.assertEqual(nxt.weekday(), 0)
        self.assertTrue(is_trading_day(nxt))
    def test_next_trading_day_midweek(self):
        tue = date(2026, 9, 1)
        nxt = next_trading_day(tue)
        self.assertEqual(nxt, date(2026, 9, 2))
        self.assertTrue(is_trading_day(nxt))
    def test_weekend_not_trading_day(self):
        sat = date(2026, 9, 5)
        self.assertFalse(is_trading_day(sat))

if __name__ == "__main__": unittest.main()
