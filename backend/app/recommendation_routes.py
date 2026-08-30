from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from .config import get_settings
from .db import SessionLocal
from .market_calendar import get_market_status
from .recommendation_model import TradeRecommendation
from .recommendation_service import generate_quant, historical_stats, import_tradingagents, update_outcomes

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
screener_router = APIRouter(prefix="/api/screener", tags=["recommendations"])
trade_ideas_router = APIRouter(prefix="/api/stocks", tags=["recommendations"])



def _stored(strategy, method=None, symbol=None):
    today = datetime.now(timezone.utc).astimezone().date()
    with SessionLocal() as db:
        query = select(TradeRecommendation).where(TradeRecommendation.trading_date == today, TradeRecommendation.strategy == strategy)
        if method: query = query.where(TradeRecommendation.method == method)
        if symbol: query = query.where(TradeRecommendation.symbol == symbol.upper())
        rows = db.execute(query.order_by(desc(TradeRecommendation.generated_at), desc(TradeRecommendation.id))).scalars().all()
        if not rows and strategy == "BPJS":
            now = datetime.now(timezone.utc)
            query = select(TradeRecommendation).where(TradeRecommendation.trading_date < today, TradeRecommendation.strategy == strategy, TradeRecommendation.valid_until >= now, TradeRecommendation.status.in_(["ACTIVE", "PREVIEW"]))
            if method: query = query.where(TradeRecommendation.method == method)
            if symbol: query = query.where(TradeRecommendation.symbol == symbol.upper())
            rows = db.execute(query.order_by(desc(TradeRecommendation.trading_date), desc(TradeRecommendation.score))).scalars().all()
    latest = {}
    for record in rows:
        latest.setdefault(record.symbol, record)
    return [_row(record) for record in sorted(latest.values(), key=lambda item: (float(item.score or 0), item.generated_at), reverse=True)]

@router.get('/strategy/{strategy}')
def strategy(strategy: str, method: str | None = None):
    if strategy not in ('GENERAL', 'BSJP', 'BPJS'):
        raise HTTPException(400, 'Invalid strategy')
    data = _stored(strategy, method)
    market = get_market_status()
    return {'strategy': strategy, 'method': method, 'data': data, 'market': market, 'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'OK' if data else 'NO_TRADE', 'reason': None if data else 'NO_QUALIFIED_SETUP'}

@router.get("/today")
def today(trading_date: str | None = None):
    d = trading_date or datetime.now(timezone.utc).astimezone().date().isoformat()
    with SessionLocal() as db:
        rows = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == d, TradeRecommendation.action != "NO_TRADE").order_by(desc(TradeRecommendation.score))).scalars().all()
        market = get_market_status()
        ta = [_row(r) for r in rows if r.method == "TRADING_AGENTS"]
        paper = [_row(r) for r in rows if r.method == "PAPER_TRADE"]
        symbols = set(r.symbol for r in rows)
        consensus = {}
        for sym in symbols:
            ta_action = next((r.action for r in rows if r.symbol == sym and r.method == "TRADING_AGENTS"), None)
            pp_action = next((r.action for r in rows if r.symbol == sym and r.method == "PAPER_TRADE"), None)
            if ta_action and pp_action:
                consensus[sym] = "STRONG" if ta_action == pp_action == "BUY" else "MIXED"
            elif ta_action or pp_action:
                consensus[sym] = "PARTIAL"
            else:
                consensus[sym] = "NOT_ANALYZED"
    return {"trading_date": d, "market": market, "generated_at": datetime.now(timezone.utc).isoformat(), "trading_agents": ta, "paper_trade": paper, "consensus": consensus, "no_trade": {"trading_agents": "NO QUALIFIED SETUP" if not ta else None, "paper_trade": "NO QUALIFIED SETUP" if not paper else None}}

@router.get("/trading-agents")
def ta_picks(trading_date: str | None = None):
    d = trading_date or datetime.now(timezone.utc).astimezone().date().isoformat()
    with SessionLocal() as db:
        rows = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == d, TradeRecommendation.method == "TRADING_AGENTS").order_by(desc(TradeRecommendation.score))).scalars().all()
    return {"trading_date": d, "data": [_row(r) for r in rows], "generated_at": datetime.now(timezone.utc).isoformat()}

@router.get("/paper")
def paper_picks(trading_date: str | None = None):
    d = trading_date or datetime.now(timezone.utc).astimezone().date().isoformat()
    with SessionLocal() as db:
        rows = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == d, TradeRecommendation.method == "PAPER_TRADE").order_by(desc(TradeRecommendation.score))).scalars().all()
    return {"trading_date": d, "data": [_row(r) for r in rows], "generated_at": datetime.now(timezone.utc).isoformat()}

@router.post("/generate/paper", status_code=202)
def gen_paper(strategy: str = Query("GENERAL"), preview: bool = Query(False)):
    if strategy not in ("GENERAL", "BSJP", "BPJS"):
        raise HTTPException(400, "Invalid strategy")
    return generate_quant(strategy, preview=preview)

@router.post("/generate/import-ta", status_code=202)
def gen_ta():
    return import_tradingagents()

@router.post("/outcomes/update")
def outcomes_update():
    return update_outcomes()

@router.get("/performance")
def perf(strategy: str = Query("GENERAL")):
    with SessionLocal() as db:
        return historical_stats(db, strategy)

@router.get('/stocks/{symbol}/trade-ideas')
def stock_trade_ideas(symbol: str):
    data = _stored('GENERAL', symbol=symbol) + _stored('BSJP', symbol=symbol) + _stored('BPJS', symbol=symbol)
    return {'symbol': symbol.upper(), 'data': data, 'market': get_market_status()}

@screener_router.get('/{strategy}')
def screener_strategy_alias(strategy: str, method: str | None = None):
    if strategy.lower() not in ('bsjp', 'bpjs'):
        raise HTTPException(404, 'Strategy screener not found')
    data = _stored(strategy.upper(), method)
    market = get_market_status()
    return {'strategy': strategy.upper(), 'method': method, 'data': data, 'market': market, 'status': 'OK' if data else 'NO_TRADE', 'reason': None if data else 'OUTSIDE_STRATEGY_WINDOW_OR_NO_QUALIFIED_SETUP', 'generated_at': datetime.now(timezone.utc).isoformat()}

@trade_ideas_router.get('/{symbol}/trade-ideas')
def stock_trade_ideas_alias(symbol: str):
    data = _stored('GENERAL', symbol=symbol) + _stored('BSJP', symbol=symbol) + _stored('BPJS', symbol=symbol)
    return {'symbol': symbol.upper(), 'data': data, 'market': get_market_status()}

def _row(r):
    return {"id": r.id, "trading_date": str(r.trading_date), "symbol": r.symbol, "method": r.method, "strategy": r.strategy, "action": r.action, "status": r.status, "current_price": r.current_price, "entry_price": r.entry_price, "entry_low": r.entry_low, "entry_high": r.entry_high, "tp1": r.tp1, "tp2": r.tp2, "stop_loss": r.stop_loss, "risk_reward": r.risk_reward, "score": r.score, "confidence": r.confidence_label, "valid_until": r.valid_until.isoformat() if r.valid_until else None, "reasons": r.reasons, "signals": r.signals, "risks": r.risks, "outcome": r.outcome, "generated_at": r.generated_at.isoformat() if r.generated_at else None, "data_timestamp": r.data_timestamp.isoformat() if r.data_timestamp else None, "market_status": r.market_status}


@router.get('/screener/{strategy}')
def screener_strategy(strategy: str, method: str | None = None):
    if strategy not in ('BSJP', 'BPJS'):
        raise HTTPException(400, 'Invalid strategy')
    data = _stored(strategy, method)
    market = get_market_status()
    return {'strategy': strategy, 'data': data, 'market': market, 'status': 'OK' if data else 'NO_TRADE', 'reason': None if data else 'OUTSIDE_STRATEGY_WINDOW_OR_NO_QUALIFIED_SETUP', 'generated_at': datetime.now(timezone.utc).isoformat()}
