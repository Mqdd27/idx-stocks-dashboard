from datetime import datetime, timezone
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal
from .recommendation_model import TradeRecommendation
from .watchlist_model import AIWatchlist
from .market_calendar import get_market_status


def _status(row, now):
    if row.status in ("EXPIRED", "SL_HIT", "TP2_HIT"): return "EXPIRED"
    if row.entry_low is None or row.entry_high is None: return "WATCH"
    if row.current_price is not None and row.current_price <= row.entry_high:
        return "NEAR_ENTRY"
    return "WAIT_ENTRY"


def generate_watchlist(now=None):
    now = now or datetime.now(timezone.utc)
    market = get_market_status(now)
    created = 0
    with SessionLocal() as db:
        recs = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == now.astimezone().date()).order_by(desc(TradeRecommendation.score))).scalars().all()
        for rec in recs:
            if rec.method not in ("TRADING_AGENTS", "PAPER_TRADE"): continue
            existing = db.execute(select(AIWatchlist).where(AIWatchlist.trading_date == rec.trading_date, AIWatchlist.symbol == rec.symbol, AIWatchlist.method == rec.method)).scalar_one_or_none()
            if existing: continue
            entry = {"entry": rec.entry_price, "low": rec.entry_low, "high": rec.entry_high, "tp1": rec.tp1, "tp2": rec.tp2, "stop_loss": rec.stop_loss, "risk_reward": rec.risk_reward}
            item = AIWatchlist(trading_date=rec.trading_date, symbol=rec.symbol, method=rec.method, status=_status(rec, now), score=rec.score, confidence=rec.confidence_label, last_price=rec.current_price, entry_price=rec.entry_price, entry_low=rec.entry_low, entry_high=rec.entry_high, tp1=rec.tp1, tp2=rec.tp2, stop_loss=rec.stop_loss, risk_reward=rec.risk_reward, generated_at=rec.generated_at, data_timestamp=rec.data_timestamp, valid_until=rec.valid_until, reasons=rec.reasons or {}, signals=rec.signals or {}, risks=rec.risks or {}, outcome={})
            db.add(item)
            try: db.commit(); created += 1
            except IntegrityError: db.rollback()
    return {"created": created, "status": market["status"], "market": market}


def refresh_status(now=None):
    now = now or datetime.now(timezone.utc)
    updated = 0
    with SessionLocal() as db:
        items = db.execute(select(AIWatchlist).where(AIWatchlist.status.in_(["WATCH", "WAIT_ENTRY", "NEAR_ENTRY", "READY"]))).scalars().all()
        for item in items:
            rec = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == item.trading_date, TradeRecommendation.symbol == item.symbol, TradeRecommendation.method == item.method).order_by(desc(TradeRecommendation.id)).limit(1)).scalar_one_or_none()
            if not rec: continue
            item.status = _status(rec, now); item.updated_at = now; updated += 1
        db.commit()
    return {"updated": updated, "timestamp": now.isoformat()}
