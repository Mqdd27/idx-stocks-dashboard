import unittest

from app.foreign_flow_service import _status, _streak, _summary


class Row:
    def __init__(self, buy, sell, volume=1000):
        self.foreign_buy_volume = buy
        self.foreign_sell_volume = sell
        self.net_foreign_volume = buy - sell
        self.total_traded_volume = volume
        self.trading_date = "2026-09-08"
        self.source = "IDX GetStockSummary"
        self.source_timestamp = None
        self.updated_at = None


class ForeignFlowServiceTest(unittest.TestCase):
    def test_net_ratio_and_cumulative_period(self):
        result = _summary([Row(700, 200), Row(100, 400)], "5d")
        self.assertEqual(result["foreign_buy_volume"], 800)
        self.assertEqual(result["foreign_sell_volume"], 600)
        self.assertEqual(result["net_foreign_volume"], 200)
        self.assertEqual(result["net_foreign_ratio"], 10)

    def test_positive_negative_zero_and_streak(self):
        self.assertEqual(_streak([Row(5, 1), Row(4, 2), Row(1, 5)]), 2)
        self.assertEqual(_streak([Row(1, 5), Row(2, 6)]), -2)
        self.assertEqual(_streak([Row(1, 1)]), 0)
        self.assertEqual(_status(10, 2, 1), "ACCUMULATION")
        self.assertEqual(_status(-10, -2, -1), "DISTRIBUTION")
        self.assertEqual(_status(0, 0, 0), "NEUTRAL")


if __name__ == "__main__":
    unittest.main()
