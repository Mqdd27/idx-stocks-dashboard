import unittest
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from app.recommendation_routes import _latest_records, _current_records
from app.performance_service import _metrics
from app.recommendation_service import update_outcomes
from app.telegram_delivery_model import TelegramDelivery

TZ = ZoneInfo("Asia/Jakarta")

class RecommendationProjectionTest(unittest.TestCase):
    """Test current/latest recommendation selection semantics."""

    def make_rec(self, symbol="BBCA", method="PAPER_TRADE", strategy="BSJP", 
                 day=date(2026, 9, 3), status="ACTIVE", cycle="daily", 
                 gen_at=None, score=80, rec_id=1):
        gen = gen_at or datetime.now(TZ)
        return SimpleNamespace(
            id=rec_id, symbol=symbol, method=method, strategy=strategy,
            trading_date=day, status=status, cycle=cycle,
            generated_at=gen, score=score, action="BUY"
        )

    def test_latest_records_picks_latest_generated(self):
        """_latest_records should pick the most recently generated per symbol/method/strategy."""
        older = self.make_rec(gen_at=datetime(2026, 9, 3, 9, 0, tzinfo=TZ), rec_id=1, score=70)
        newer = self.make_rec(gen_at=datetime(2026, 9, 3, 10, 0, tzinfo=TZ), rec_id=2, score=90)
        result = _latest_records([older, newer])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 2)  # newer wins

    def test_latest_records_different_symbols_independent(self):
        """Different symbols should each get their latest."""
        a1 = self.make_rec(symbol="BBCA", gen_at=datetime(2026, 9, 3, 9, 0, tzinfo=TZ), rec_id=1)
        a2 = self.make_rec(symbol="BBCA", gen_at=datetime(2026, 9, 3, 10, 0, tzinfo=TZ), rec_id=2)
        b1 = self.make_rec(symbol="BBRI", gen_at=datetime(2026, 9, 3, 9, 0, tzinfo=TZ), rec_id=3)
        result = _latest_records([a1, a2, b1])
        self.assertEqual(len(result), 2)
        ids = {r.id for r in result}
        self.assertEqual(ids, {2, 3})

    def test_current_records_prefers_live_over_preview(self):
        """_current_records should rank LIVE (non-preview) above PREVIEW when same day."""
        preview = self.make_rec(status="PREVIEW", cycle="preview", gen_at=datetime(2026, 9, 3, 10, 0, tzinfo=TZ), rec_id=1)
        live = self.make_rec(status="ACTIVE", cycle="daily", gen_at=datetime(2026, 9, 3, 9, 0, tzinfo=TZ), rec_id=2)
        result = _current_records([preview, live])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 2)  # LIVE wins despite older gen_at

    def test_current_records_live_beats_newer_preview(self):
        """LIVE beats newer PREVIEW (original behavior)."""
        old_live = self.make_rec(status="ACTIVE", cycle="daily", gen_at=datetime(2026, 9, 3, 8, 0, tzinfo=TZ), rec_id=1)
        new_preview = self.make_rec(status="PREVIEW", cycle="preview", gen_at=datetime(2026, 9, 3, 10, 0, tzinfo=TZ), rec_id=2)
        result = _current_records([old_live, new_preview])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)  # LIVE wins despite older gen_at

    def test_current_records_different_methods_independent(self):
        """PAPER_TRADE and TRADING_AGENTS tracked independently."""
        ta = self.make_rec(method="TRADING_AGENTS", gen_at=datetime(2026, 9, 3, 10, 0, tzinfo=TZ), rec_id=1)
        paper = self.make_rec(method="PAPER_TRADE", gen_at=datetime(2026, 9, 3, 9, 0, tzinfo=TZ), rec_id=2)
        result = _current_records([ta, paper])
        self.assertEqual(len(result), 2)
        ids = {r.id for r in result}
        self.assertEqual(ids, {1, 2})

    def test_current_records_preview_in_cycle_name(self):
        """cycle containing preview should be treated as preview."""
        preview_cycle = self.make_rec(status="ACTIVE", cycle="night-preview", gen_at=datetime(2026, 9, 3, 10, 0, tzinfo=TZ), rec_id=1)
        live_cycle = self.make_rec(status="ACTIVE", cycle="daily", gen_at=datetime(2026, 9, 3, 9, 0, tzinfo=TZ), rec_id=2)
        result = _current_records([preview_cycle, live_cycle])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 2)  # live wins

if __name__ == "__main__":
    unittest.main()
