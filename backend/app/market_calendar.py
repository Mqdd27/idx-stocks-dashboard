from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .db import SessionLocal
from . import models

TZ=ZoneInfo("Asia/Jakarta")
class MarketStatus(StrEnum):
    OPEN="OPEN"; CLOSED="CLOSED"; PRE_OPEN="PRE_OPEN"; BREAK="BREAK"; POST_MARKET="POST_MARKET"; WEEKEND="WEEKEND"; PUBLIC_HOLIDAY="PUBLIC_HOLIDAY"; EXCHANGE_HOLIDAY="EXCHANGE_HOLIDAY"
@dataclass(frozen=True)
class SessionWindow:
    name:str; start:time; end:time

# IDX regular equity sessions; update here when IDX publishes a new schedule.
SESSIONS=(SessionWindow("PRE_OPEN",time(8,45),time(9,0)),SessionWindow("SESSION_1",time(9,0),time(12,0)),SessionWindow("BREAK",time(12,0),time(13,30)),SessionWindow("SESSION_2",time(13,30),time(15,50)),SessionWindow("POST_MARKET",time(15,50),time(16,0)))

def today_jakarta(): return datetime.now(TZ).date()

def localize(value):
    if value is None: return datetime.now(TZ)
    return value.astimezone(TZ) if value.tzinfo else value.replace(tzinfo=TZ)
def _holiday(day):
    db=SessionLocal()
    try:
        return db.execute(select(models.MarketHoliday).where(models.MarketHoliday.market=="IDX",models.MarketHoliday.date==day)).scalar_one_or_none()
    finally: db.close()
def _override(day):
    db=SessionLocal()
    try:
        return db.execute(select(models.MarketCalendarOverride).where(models.MarketCalendarOverride.market=="IDX",models.MarketCalendarOverride.date==day)).scalar_one_or_none()
    finally: db.close()
def is_trading_day(day):
    if day.weekday()>=5:return False
    h=_holiday(day); o=_override(day)
    return bool(o.is_trading_day) if o else not (h and not h.is_trading_day)
def _next(day,step=1):
    day+=timedelta(days=step)
    while not is_trading_day(day): day+=timedelta(days=step)
    return day
def next_trading_day(day): return _next(day)
def previous_trading_day(day): return _next(day,-1)
def get_trading_sessions(day):
    if not is_trading_day(day):
        return []
    o = _override(day)
    if not o:
        return list(SESSIONS)
    open_time = o.open_time or SESSIONS[0].start
    close_time = o.close_time or SESSIONS[-1].end
    return (
        SessionWindow("PRE_OPEN", open_time, SESSIONS[0].end),
        SessionWindow("SESSION_1", SESSIONS[1].start, o.session_1_end or SESSIONS[1].end),
        SessionWindow("BREAK", SESSIONS[2].start, SESSIONS[2].end),
        SessionWindow("SESSION_2", o.session_2_start or SESSIONS[3].start, close_time),
        SessionWindow("POST_MARKET", close_time, close_time),
    )
def get_holiday(day): return _holiday(day)
def get_market_status(value=None):
    now=localize(value); day=now.date(); h=_holiday(day); o=_override(day); sessions=get_trading_sessions(day)
    if day.weekday()>=5: status,reason=MarketStatus.WEEKEND,"Weekend"
    elif h and not (o and o.is_trading_day): status,reason=MarketStatus(h.holiday_type),h.name
    elif o and not o.is_trading_day: status,reason=MarketStatus.EXCHANGE_HOLIDAY,o.reason or "IDX Exchange Holiday"
    elif not is_trading_day(day): status,reason=MarketStatus.EXCHANGE_HOLIDAY,"IDX Exchange Holiday"
    else:
        status,reason=MarketStatus.CLOSED,"Outside trading session"
        for s in sessions:
            if s.start<=now.time()<s.end: status=s.name; reason=""
    next_session = next((session for session in sessions if now.time() < session.start), None)
    nxt = day if next_session else _next(day)
    next_sessions=get_trading_sessions(nxt)
    opening=datetime.combine(nxt, (next_session or next_sessions[0]).start, tzinfo=TZ)
    status_value = status.value if isinstance(status, MarketStatus) else status
    return {"market":"IDX","status":status_value,"is_open":status_value in ("OPEN","SESSION_1","SESSION_2"),"is_trading_day":is_trading_day(day),"timezone":"Asia/Jakarta","current_session":status_value if status_value in ("PRE_OPEN","SESSION_1","BREAK","SESSION_2","POST_MARKET") else None,"reason":reason,"date":day.isoformat(),"current_time":now.isoformat(),"next_trading_day":nxt.isoformat(),"next_market_open":opening.isoformat(),"next_event_time":opening.isoformat()}
def is_market_open(value=None): return get_market_status(value)["is_open"]
def is_market_hours(value=None): return get_market_status(value)["status"] in ("SESSION_1","SESSION_2")
def next_market_open(value=None): return datetime.fromisoformat(get_market_status(value)["next_market_open"])
