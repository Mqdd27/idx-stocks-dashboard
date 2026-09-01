import os
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

class SecurityTimezoneTest(unittest.TestCase):
    def setUp(self):
        os.environ["ADMIN_API_TOKEN"] = "audit-test-token"
        os.environ["CORS_ALLOWED_ORIGINS"] = "https://stocks.mqdd.my.id,http://localhost:3100"
        os.environ["AI_TRADING_ENABLED"] = "false"
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("ADMIN_API_TOKEN", None)
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)
        os.environ.pop("AI_TRADING_ENABLED", None)

    def test_public_read_and_protected_write(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.post("/api/ai-trading/batches", json={"batch_size": 1}).status_code, 401)
        self.assertEqual(self.client.post("/api/ai-trading/batches", json={"batch_size": 1}, headers={"Authorization": "Bearer audit-test-token"}).status_code, 503)

    def test_cors_allowlist(self):
        bad = self.client.options("/api/stocks", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
        good = self.client.options("/api/stocks", headers={"Origin": "https://stocks.mqdd.my.id", "Access-Control-Request-Method": "GET"})
        self.assertNotEqual(bad.headers.get("access-control-allow-origin"), "https://evil.example")
        self.assertEqual(good.headers.get("access-control-allow-origin"), "https://stocks.mqdd.my.id")

    def test_jakarta_date_is_independent_of_machine_timezone(self):
        from app.market_calendar import TZ, today_jakarta
        self.assertEqual(TZ, ZoneInfo("Asia/Jakarta"))
        self.assertEqual(today_jakarta(), datetime.now(ZoneInfo("Asia/Jakarta")).date())

if __name__ == "__main__":
    unittest.main()
