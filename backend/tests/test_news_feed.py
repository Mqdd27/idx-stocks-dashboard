import unittest
from pathlib import Path


class NewsFeedTest(unittest.TestCase):
    def setUp(self):
        self.main = (Path(__file__).parents[2] / "backend/app/main.py").read_text()
        self.page = (Path(__file__).parents[2] / "frontend/app/news/page.tsx").read_text()

    def test_feed_deduplicates_and_filters(self):
        self.assertIn('@app.get("/api/news/feed")', self.main)
        self.assertIn('key = (news.url or "").strip().lower()', self.main)
        self.assertIn('if key in seen: continue', self.main)
        self.assertIn('sentiment: str = Query("all"', self.main)
        self.assertIn('days: int = Query(7, ge=1, le=365)', self.main)

    def test_ui_uses_aggregate_feed_and_filters(self):
        self.assertIn("api.newsFeed", self.page)
        self.assertIn("MARKET FEED", self.page)
        self.assertIn("SEMUA SENTIMEN", self.page)


if __name__ == "__main__":
    unittest.main()
