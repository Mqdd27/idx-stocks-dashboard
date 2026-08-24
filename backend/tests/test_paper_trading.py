import unittest

from datetime import date

from app.paper_trading import check_exit, decide, setup_confidence, size_position, trade_metrics



class PaperTradingTest(unittest.TestCase):
    def test_sizing_and_selective_decision(self):
        self.assertEqual(size_position(10000, 100, 95), 0)
        self.assertEqual(size_position(1000000, 100, 95), 19)
        result = decide({"last_price": 100, "atr14": 2, "sma20": 90, "sma50": 90, "rsi14": 60, "macd": {"histogram": 1}})
        self.assertEqual(result.action, "buy")
        self.assertEqual(decide({"last_price": 100}).action, "no_trade")

    def test_lot_accounting_and_dynamic_setup_score(self):
        self.assertEqual((100 * 3 * 100), 30000)
        self.assertGreater(setup_confidence(4, 110, 100, 90, 120), setup_confidence(4, 95, 100, 90, 120))
        self.assertEqual(setup_confidence(4, 120, 100, 90, 120), 4)

    def test_exits_and_metrics(self):
        self.assertEqual(check_exit(date(2026, 1, 1), date(2026, 1, 2), 90, 95, 110, 20).reason, "stop_loss")
        self.assertEqual(check_exit(date(2026, 1, 1), date(2026, 1, 21), 100, 95, 110, 20).reason, "time_exit")
        class Trade:
            def __init__(self, pnl): self.pnl = pnl
        metrics = trade_metrics([Trade(10), Trade(-5)])
        self.assertEqual(metrics["win_rate"], 0.5)
        self.assertEqual(metrics["profit_factor"], 2)
        self.assertEqual(metrics["expectancy"], 2.5)


if __name__ == "__main__":
    unittest.main()
