import unittest
from datetime import date
from types import SimpleNamespace
from app.performance_service import _metrics, period_bounds

class PerformanceServiceTest(unittest.TestCase):
    def row(self, strategy="BSJP", method="PAPER_TRADE", day=date(2026, 9, 4), status="TP2_HIT", entered=True, value=2, exit_date="2026-09-07"):
        return SimpleNamespace(strategy=strategy, method=method, trading_date=day, status=status, outcome={"entry_triggered": entered, "return_pct": value, "exit_date": exit_date})
    def test_period_bounds(self):
        self.assertEqual(period_bounds("weekly", date(2026, 9, 4)), (date(2026, 8, 31), date(2026, 9, 6)))
        self.assertEqual(period_bounds("monthly", date(2026, 9, 4))[0], date(2026, 9, 1))
        self.assertEqual(period_bounds("yearly", date(2026, 9, 4))[0], date(2026, 1, 1))
    def test_bsjp_cross_day_counted_once_by_entry_date(self):
        row=self.row(exit_date="2026-09-07")
        self.assertEqual(_metrics([row], "BSJP", "PAPER_TRADE", "daily", date(2026,9,4), date(2026,9,4))["trades"], 1)
        self.assertEqual(_metrics([row], "BSJP", "PAPER_TRADE", "daily", date(2026,9,7), date(2026,9,7))["trades"], 0)
    def test_bpjs_overnight_anomaly_excluded(self):
        result=_metrics([self.row("BPJS", exit_date="2026-09-07")], "BPJS", "PAPER_TRADE", "daily", date(2026,9,4), date(2026,9,4))
        self.assertEqual(result["trades"], 0); self.assertEqual(result["anomalies"], 1)
    def test_metrics_and_exclusions(self):
        rows=[self.row(value=10,exit_date="2026-09-04"),self.row(value=-5,exit_date="2026-09-04"),self.row(value=0,exit_date="2026-09-04"),self.row(status="ACTIVE",value=4,exit_date=None),self.row(status="EXPIRED",entered=False,value=None,exit_date=None)]
        result=_metrics(rows,"BSJP","PAPER_TRADE","daily",date(2026,9,4),date(2026,9,4))
        self.assertEqual(result["trades"],3); self.assertEqual(result["winning_trades"],1); self.assertEqual(result["losing_trades"],1); self.assertEqual(result["breakeven_trades"],1); self.assertEqual(result["signals"],5); self.assertEqual(result["open_positions"],1); self.assertEqual(result["not_triggered"],1); self.assertAlmostEqual(result["profit_factor"],2); self.assertAlmostEqual(result["net_return_pct"],4.5)

if __name__ == "__main__": unittest.main()
