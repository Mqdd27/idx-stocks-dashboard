import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.market_calendar import get_market_status
TZ=ZoneInfo('Asia/Jakarta')
class CalendarTest(unittest.TestCase):
    def test_weekend(self):
        result=get_market_status(datetime(2026,8,22,10,tzinfo=TZ))
        self.assertEqual(result['status'],'WEEKEND')
    def test_session(self):
        result=get_market_status(datetime(2026,8,24,10,tzinfo=TZ))
        self.assertEqual(result['status'],'SESSION_1')
if __name__=='__main__': unittest.main()
