from datetime import datetime, date
from unittest.mock import patch
from zoneinfo import ZoneInfo
from app.market_calendar import get_market_status, next_trading_day, previous_trading_day

TZ=ZoneInfo('Asia/Jakarta')
def test_weekend_and_timezone():
    s=get_market_status(datetime(2026,8,22,3,tzinfo=ZoneInfo('UTC')))
    assert s['status']=='WEEKEND'
def test_sessions():
    assert get_market_status(datetime(2026,8,24,10,tzinfo=TZ))['status']=='SESSION_1'
    assert get_market_status(datetime(2026,8,24,12,30,tzinfo=TZ))['status']=='BREAK'
    assert get_market_status(datetime(2026,8,24,14,tzinfo=TZ))['status']=='SESSION_2'
def test_year_boundary():
    assert next_trading_day(date(2026,12,31)) == date(2027,1,1)
    assert previous_trading_day(date(2027,1,1)) == date(2026,12,31)
def test_exchange_holiday_override():
    class H: holiday_type='EXCHANGE_HOLIDAY'; name='IDX Holiday'; is_trading_day=False
    with patch('app.market_calendar._holiday', return_value=H()), patch('app.market_calendar._override', return_value=None):
        assert get_market_status(datetime(2026,8,24,10,tzinfo=TZ))['status']=='EXCHANGE_HOLIDAY'
