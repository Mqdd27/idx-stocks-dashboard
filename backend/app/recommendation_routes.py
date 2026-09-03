from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from .config import get_settings
from .db import SessionLocal
from .market_calendar import TZ, get_market_status
from .recommendation_model import TradeRecommendation
from .recommendation_service import generate_quant, historical_stats, import_tradingagents, update_outcomes
from .telegram_delivery_model import TelegramDelivery
from .performance_service import get_performance, get_trade_drilldown

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
screener_router = APIRouter(prefix="/api/screener", tags=["recommendations"])
trade_ideas_router = APIRouter(prefix="/api/stocks", tags=["recommendations"])





def _latest_records(records):
    latest = {}
    for record in records:
        key = (record.symbol, record.method, record.strategy)
        current = latest.get(key)
        if current is None or (record.generated_at, record.id) > (current.generated_at, current.id):
            latest[key] = record
    return list(latest.values())

def _current_records(records):
    current = {}
    for record in records:
        key = (record.symbol, record.method, record.strategy)
        preview = record.status == "PREVIEW" or "preview" in (record.cycle or "").lower()
        existing = current.get(key)
        rank = (0 if preview else 1, record.generated_at, record.id)
        existing_rank = (-1, datetime.min, -1) if existing is None else (0 if existing.status == "PREVIEW" or "preview" in (existing.cycle or "").lower() else 1, existing.generated_at, existing.id)
        if existing is None or rank > existing_rank:
            current[key] = record
    return list(current.values())

def _stored(strategy, method=None, symbol=None, trading_date=None):
    today = trading_date or datetime.now(TZ).date()
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
    latest = _current_records(rows)
    return [_row(record) for record in sorted(latest, key=lambda item: (float(item.score or 0), item.generated_at), reverse=True)]

@router.get('/strategy/{strategy}')
def strategy(strategy: str, method: str | None = None, trading_date: str | None = None):
    if strategy not in ('GENERAL', 'BSJP', 'BPJS'):
        raise HTTPException(400, 'Invalid strategy')
    data = _stored(strategy, method, trading_date=trading_date)
    market = get_market_status()
    return {'strategy': strategy, 'method': method, 'data': data, 'market': market, 'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'OK' if data else 'NO_TRADE', 'reason': None if data else 'NO_QUALIFIED_SETUP'}

@router.get("/today")
def today(trading_date: str | None = None):
    d = trading_date or datetime.now(TZ).date().isoformat()
    with SessionLocal() as db:
        rows = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == d, TradeRecommendation.action != "NO_TRADE").order_by(desc(TradeRecommendation.generated_at), desc(TradeRecommendation.id))).scalars().all()
        rows = _latest_records(rows)
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
    d = trading_date or datetime.now(TZ).date().isoformat()
    return {"trading_date": d, "data": _stored("GENERAL", "TRADING_AGENTS", trading_date=d), "generated_at": datetime.now(timezone.utc).isoformat()}

@router.get("/paper")
def paper_picks(trading_date: str | None = None):
    d = trading_date or datetime.now(TZ).date().isoformat()
    return {"trading_date": d, "data": _stored("GENERAL", "PAPER_TRADE", trading_date=d), "generated_at": datetime.now(timezone.utc).isoformat()}

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

@router.get("/notifications/status")
def notification_status():
    with SessionLocal() as db:
        rows = db.execute(select(TelegramDelivery).order_by(desc(TelegramDelivery.generated_at)).limit(20)).scalars().all()
    return {"owner": "Hermes", "data": [{"id": r.id, "message_type": r.message_type, "target_date": r.target_date, "cycle": r.cycle, "status": r.status, "attempt_count": r.attempt_count, "telegram_message_id": r.telegram_message_id, "last_error": r.last_error, "generated_at": r.generated_at, "sent_at": r.sent_at} for r in rows]}

@router.get("/strategy-performance/{strategy}")
def strategy_performance(strategy: str, period: str = Query("daily"), method: str | None = None, date: str | None = None):
    from datetime import date as date_type
    with SessionLocal() as db:
        return get_performance(db, strategy.upper(), period, date_type.fromisoformat(date) if date else None, method)

@router.get("/strategy-performance/{strategy}/trades")
def strategy_performance_trades(strategy: str, period: str = Query("monthly"), method: str | None = None, date: str | None = None):
    from datetime import date as date_type
    with SessionLocal() as db:
        return get_trade_drilldown(db, strategy.upper(), period, date_type.fromisoformat(date) if date else None, method)

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
    return {"id": r.id, "trading_date": str(r.trading_date), "symbol": r.symbol, "method": r.method, "strategy": r.strategy, "mode": "PREVIEW" if r.status == "PREVIEW" or (r.strategy == "BPJS" and "preview" in (r.cycle or "").lower()) else "LIVE", "action": r.action, "status": r.status, "current_price": r.current_price, "entry_price": r.entry_price, "entry_low": r.entry_low, "entry_high": r.entry_high, "tp1": r.tp1, "tp2": r.tp2, "stop_loss": r.stop_loss, "risk_reward": r.risk_reward, "score": r.score, "confidence": r.confidence_label, "valid_until": r.valid_until.isoformat() if r.valid_until else None, "reasons": r.reasons, "signals": r.signals, "risks": r.risks, "outcome": r.outcome, "generated_at": r.generated_at.isoformat() if r.generated_at else None, "data_timestamp": r.data_timestamp.isoformat() if r.data_timestamp else None, "market_status": r.market_status}


@router.get('/screener/{strategy}')
def screener_strategy(strategy: str, method: str | None = None):
    if strategy not in ('BSJP', 'BPJS'):
        raise HTTPException(400, 'Invalid strategy')
    data = _stored(strategy, method)
    market = get_market_status()
    result_status = 'OK' if data else 'NO_TRADE'
    reason = None if data else 'NO_QUALIFIED_SETUP'
    if not data and method == 'TRADING_AGENTS':
        paper = _stored(strategy, 'PAPER_TRADE')
        if paper:
            result_status = 'PENDING_ANALYSIS'
            reason = 'PAPER_SHORTLIST_READY_TRADINGAGENTS_PENDING'
        elif not get_settings().ai_trading_enabled:
            result_status = 'DISABLED'
            reason = 'AI_TRADING_DISABLED'
        else:
            result_status = 'NO_ANALYSIS'
            reason = 'NO_PAPER_SHORTLIST'
    return {'strategy': strategy, 'method': method, 'data': data, 'market': market, 'status': result_status, 'reason': reason, 'generated_at': datetime.now(timezone.utc).isoformat()}
