import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.paper_trading import size_position
from app.risk_service import APPROVE, REJECT, create_plan


class RiskShadowTest(unittest.TestCase):
    def test_canonical_paper_sizing_is_lot_rounded(self):
        self.assertEqual(size_position(1_000_000, 100, 95), 19)
        self.assertEqual(size_position(1_000_000, 100, 100), 0)

    def test_approved_decision_creates_shadow_plan(self):
        proposal = SimpleNamespace(
            id=7,
            recommendation_id=9,
            symbol="BBCA",
            strategy="GENERAL",
            method="PAPER_TRADE",
            reference_price=100.0,
            entry_min=98.0,
            entry_max=102.0,
            suggested_tp1=110.0,
            suggested_tp2=120.0,
        )
        decision = SimpleNamespace(
            id=8,
            decision=APPROVE,
            position_size_lots=10,
            risk_amount=5_000.0,
            stop_price=95.0,
            risk_reward_ratio=2.0,
        )
        recommendation = SimpleNamespace(id=9, valid_until=datetime.now(timezone.utc) + timedelta(days=1))
        plan = create_plan(proposal, decision, recommendation)
        self.assertEqual(plan.status, "PENDING")
        self.assertTrue(plan.is_shadow)
        self.assertEqual(plan.execution_key, "recommendation:9")
        self.assertEqual(plan.expected_reward, 10_000.0)

    def test_rejected_decision_has_no_executable_plan(self):
        proposal = SimpleNamespace()
        decision = SimpleNamespace(decision=REJECT)
        self.assertIsNone(create_plan(proposal, decision, SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()
