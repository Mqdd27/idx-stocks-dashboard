import unittest
from pathlib import Path


class NewsPageContractTest(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).parents[2] / "frontend/app/news/page.tsx"
        self.api = Path(__file__).parents[2] / "frontend/lib/api.ts"

    def test_selecting_stock_loads_news(self):
        page = self.source.read_text()
        self.assertIn("}, [selected, refreshKey]);", page)
        self.assertIn("api.news(selected, refreshKey > 0 ? refreshKey : undefined)", page)

    def test_default_feed_uses_watchlist_then_top_gainer(self):
        page = self.source.read_text()
        self.assertIn("Promise.all([api.watchlist(), api.overview()])", page)
        self.assertIn("watchlist.data[0]?.symbol || overview.gainers[0]?.symbol", page)

    def test_refresh_bypasses_news_cache(self):
        api = self.api.read_text()
        self.assertIn("news: (symbol: string, refresh?: number)", api)
        self.assertIn("?refresh=", api)


if __name__ == "__main__":
    unittest.main()
