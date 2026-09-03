import unittest
from unittest.mock import patch
from app import calendar_sync_service

class CalendarSyncServiceTest(unittest.TestCase):
    def test_primary_url_is_preferred_when_configured(self):
        with patch.dict("os.environ", {"IDX_CALENDAR_URL": "https://idx.example/{year}"}):
            with patch.object(calendar_sync_service, "_fetch", return_value=[{"date": "2026-01-01"}]):
                with patch.object(calendar_sync_service, "SessionLocal") as session:
                    session.return_value.execute.return_value.scalar_one_or_none.return_value = None
                    result = calendar_sync_service.sync_calendar(2026)
        self.assertEqual(result["source"], "IDX")
        self.assertEqual(result["count"], 1)

    def test_fallback_used_when_idx_unavailable(self):
        calls = []
        def fetch(url):
            calls.append(url)
            if "idx.example" in url:
                raise RuntimeError("idx unavailable")
            return [{"date": "2026-05-01", "localName": "Hari Buruh"}]
        with patch.dict("os.environ", {"IDX_CALENDAR_URL": "https://idx.example/{year}"}):
            with patch.object(calendar_sync_service, "_fetch", side_effect=fetch):
                with patch.object(calendar_sync_service, "SessionLocal") as session:
                    session.return_value.execute.return_value.scalar_one_or_none.return_value = None
                    result = calendar_sync_service.sync_calendar(2026)
        self.assertEqual(result["source"], "Nager.Date Indonesia public holiday fallback")
        self.assertEqual(len(calls), 2)

if __name__ == "__main__": unittest.main()
