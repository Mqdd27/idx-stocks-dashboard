import unittest
from pathlib import Path


class DataQualityContractTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parents[2]
        self.service = (root / "backend/app/data_quality_service.py").read_text()
        self.recommendations = (root / "backend/app/recommendation_service.py").read_text()
        self.operations = (root / "frontend/app/operations/page.tsx").read_text()

    def test_tracks_all_required_sources(self):
        for source in ("price", "news", "ratios", "collector"):
            self.assertIn(f'"{source}"', self.service)
        self.assertIn("PRICE_MAX_AGE", self.service)
        self.assertIn("NEWS_MAX_AGE", self.service)
        self.assertIn("RATIOS_MAX_AGE", self.service)

    def test_only_critical_open_market_data_blocks_recommendations(self):
        self.assertIn("critical_data_stale", self.recommendations)
        self.assertIn('"CRITICAL_DATA_STALE"', self.recommendations)
        self.assertIn('market.get("is_open")', self.service)

    def test_operations_shows_quality_status(self):
        self.assertIn("DATA QUALITY", self.operations)
        self.assertIn("Rekomendasi diblokir", self.operations)


if __name__ == "__main__":
    unittest.main()
