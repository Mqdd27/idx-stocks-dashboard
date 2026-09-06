import ast
import unittest
from pathlib import Path


class MarketOverviewPerformanceTest(unittest.TestCase):
    def test_overview_builds_market_universe_once(self):
        tree = ast.parse((Path(__file__).parents[2] / "backend/app/main.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "market_overview")
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_market_rows"]
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
