import unittest
from app.quant_setup import build_quant_setup

class QuantSetupTest(unittest.TestCase):
    def test_builds_deterministic_setup(self):
        setup = build_quant_setup(100, 10, 80, 130, min_rr=1.5, target_rr=2)
        self.assertEqual(setup["entry"], 100)
        self.assertEqual(setup["stop"], 85)
        self.assertEqual(setup["tp1"], 130)
        self.assertEqual(setup["tp2"], 130)
        self.assertEqual(setup["rr"], 2)
    def test_rejects_missing_atr(self):
        self.assertIsNone(build_quant_setup(100, 0, 80, 130))
    def test_falls_back_to_minimum_target(self):
        setup = build_quant_setup(100, 10, 80, 105, min_rr=1.5)
        self.assertEqual(setup["tp1"], 122.5)

if __name__ == "__main__": unittest.main()
