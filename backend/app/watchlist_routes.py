from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, select
from .db import SessionLocal
from .market_calendar import get_market_status
from .watchlist_model import AIWatchlist
from .watchlist_service import generate_watchlist, refresh_status

router = APIRouter(prefix="/api/ai-watchlist", tags=["ai-watchlist"])

def row(item):
    return {"id":item.id,"trading_date":str(item.trading_date),"symbol":item.symbol,"method":item.method,"status":item.status,"score":item.score,"confidence":item.confidence,"last_price":item.last_price,"entry_price":item.entry_price,"entry_low":item.entry_low,"entry_high":item.entry_high,"tp1":item.tp1,"tp2":item.tp2,"stop_loss":item.stop_loss,"risk_reward":item.risk_reward,"generated_at":item.generated_at.isoformat() if item.generated_at else None,"updated_at":item.updated_at.isoformat() if item.updated_at else None,"data_timestamp":item.data_timestamp.isoformat() if item.data_timestamp else None,"valid_until":item.valid_until.isoformat() if item.valid_until else None,"reasons":item.reasons,"signals":item.signals,"risks":item.risks,"outcome":item.outcome}

@router.get("/today")
def today():
    d=datetime.now(timezone.utc).astimezone().date()
    with SessionLocal() as db:
        items=db.execute(select(AIWatchlist).where(AIWatchlist.trading_date==d).order_by(desc(AIWatchlist.score))).scalars().all()
    return {"trading_date":str(d),"market":get_market_status(),"generated_at":datetime.now(timezone.utc).isoformat(),"data":[row(x) for x in items],"status":"OK" if items else "NO_TRADE","reason":None if items else "NO_QUALIFIED_WATCHLIST_CANDIDATES_TODAY"}

@router.get("/trading-agents")
def trading_agents():
    return {"method":"TRADING_AGENTS","data":[row(x) for x in _items("TRADING_AGENTS")],"market":get_market_status()}

@router.get("/paper")
def paper():
    return {"method":"PAPER_TRADE","data":[row(x) for x in _items("PAPER_TRADE")],"market":get_market_status()}

@router.get("/history")
def history(limit:int=50):
    with SessionLocal() as db:
        items=db.execute(select(AIWatchlist).order_by(desc(AIWatchlist.trading_date),desc(AIWatchlist.score)).limit(min(limit,200))).scalars().all()
    return {"data":[row(x) for x in items]}

@router.get("/{symbol}")
def symbol(symbol:str):
    with SessionLocal() as db:
        items=db.execute(select(AIWatchlist).where(AIWatchlist.symbol==symbol.upper()).order_by(desc(AIWatchlist.trading_date),desc(AIWatchlist.generated_at)).limit(20)).scalars().all()
    return {"symbol":symbol.upper(),"data":[row(x) for x in items],"market":get_market_status()}

@router.post("/refresh")
def refresh():
    return {"generation":generate_watchlist(),"status":refresh_status()}

def _items(method):
    d=datetime.now(timezone.utc).astimezone().date()
    with SessionLocal() as db:
        return db.execute(select(AIWatchlist).where(AIWatchlist.trading_date==d,AIWatchlist.method==method).order_by(desc(AIWatchlist.score))).scalars().all()
