import unittest
from pathlib import Path


class NewsReliabilityContractTest(unittest.TestCase):
    def setUp(self):
        self.page = (Path(__file__).parents[2] / "frontend/app/news/page.tsx").read_text()

    def test_retry_is_limited(self):
        self.assertIn("const RETRIES = [800, 1600]", self.page)
        self.assertIn("attempt <= RETRIES.length", self.page)

    def test_errors_are_not_rendered_as_empty_news(self):
        self.assertIn("NEWS FEED GAGAL DIMUAT", self.page)
        self.assertIn("COBA LAGI", self.page)
        self.assertIn("feedError ? <ErrorState", self.page)
        self.assertIn("stockError ? <ErrorState", self.page)

    def test_tab_shows_relevant_success_or_failure_status(self):
        self.assertIn('tab === "stock"', self.page)
        self.assertIn("Stock: ${updatedAt ?", self.page)
        self.assertIn("Market: ${feedUpdatedAt ?", self.page)


if __name__ == "__main__":
    unittest.main()
