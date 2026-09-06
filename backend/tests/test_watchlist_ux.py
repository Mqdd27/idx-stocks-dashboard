import unittest
from pathlib import Path


class WatchlistUxContractTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parents[2]
        self.backend = (root / "backend/app/main.py").read_text()
        self.page = (root / "frontend/app/watchlist/page.tsx").read_text()

    def test_api_supports_note_reorder_and_latest_news(self):
        self.assertIn('action == "update"', self.backend)
        self.assertIn('action == "reorder"', self.backend)
        self.assertIn('"latest_news"', self.backend)

    def test_ui_uses_native_drag_and_local_alerts(self):
        self.assertIn("draggable", self.page)
        self.assertIn("onDrop={() => reorder(it.symbol)}", self.page)
        self.assertIn("stocks.watchlist.alerts", self.page)
        self.assertIn("latest_news", self.page)


if __name__ == "__main__":
    unittest.main()
