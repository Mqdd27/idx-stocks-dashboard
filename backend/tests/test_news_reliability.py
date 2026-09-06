import unittest
from pathlib import Path


class NewsReliabilityContractTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parents[2]
        self.page = (root / "frontend/app/news/page.tsx").read_text()
        self.content = (root / "frontend/components/NewsContent.tsx").read_text()

    def test_retry_is_limited(self):
        self.assertIn("const RETRIES = [800, 1600]", self.page)
        self.assertIn("attempt <= RETRIES.length", self.page)

    def test_errors_are_not_rendered_as_empty_news(self):
        self.assertIn("NEWS FEED GAGAL DIMUAT", self.content)
        self.assertIn("COBA LAGI", self.content)
        self.assertIn("<NewsError message={error} onRetry={onRetry} />", self.page)

    def test_tab_shows_relevant_success_or_failure_status(self):
        self.assertIn('tab === "stock"', self.page)
        self.assertIn("Stock: ${status(updatedAt, stockError)}", self.page)
        self.assertIn("Market: ${status(feedUpdatedAt, feedError)}", self.page)


if __name__ == "__main__":
    unittest.main()
