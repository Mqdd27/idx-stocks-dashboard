import unittest
from pathlib import Path


class PaperDecisionCardTest(unittest.TestCase):
    def test_card_uses_existing_data_without_creating_trades(self):
        root = Path(__file__).parents[2]
        card = (root / "frontend/components/PaperDecisionCard.tsx").read_text()
        page = (root / "frontend/components/StockDetailPage.tsx").read_text()
        self.assertIn("PAPER-ONLY", card)
        self.assertIn("api.stockTradeIdeas(symbol)", card)
        self.assertIn("api.news(symbol)", card)
        self.assertNotIn("paperRun", card)
        self.assertIn("<PaperDecisionCard", page)


if __name__ == "__main__":
    unittest.main()
