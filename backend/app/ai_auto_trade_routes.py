import asyncio

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select

from .ai_auto_trade import execute_run, get_config
from .ai_auto_trade_model import AIAutoTradeRun
from .config import get_settings
from .db import SessionLocal
from .market_calendar import get_market_status
from .models import PaperBotConfig, PaperTrade

router = APIRouter(prefix="/api/ai-auto-trade", tags=["ai-auto-trade"])


@router.get("/status")
def status():
    with SessionLocal() as db:
        config = get_config(db)
        paper = db.execute(select(PaperBotConfig).limit(1)).scalar_one_or_none()
        active = db.execute(select(AIAutoTradeRun).where(AIAutoTradeRun.status.in_(["QUEUED", "RUNNING"])).order_by(desc(AIAutoTradeRun.id)).limit(1)).scalar_one_or_none()
        open_count = len(db.execute(select(PaperTrade).where(PaperTrade.status == "open")).scalars().all())
        return {
            "enabled": config.enabled,
            "ai_trading_enabled": get_settings().ai_trading_enabled,
            "paper_trading_enabled": bool(paper and paper.enabled),
            "max_candidates": config.max_candidates,
            "quick_model": config.quick_model,
            "deep_model": config.deep_model,
            "market": get_market_status(),
            "active_run_id": active.id if active else None,
            "open_positions": open_count,
            "paper_only": True,
        }


@router.get("/runs")
def runs(limit: int = 30):
    with SessionLocal() as db:
        rows = db.execute(select(AIAutoTradeRun).order_by(desc(AIAutoTradeRun.id)).limit(min(limit, 100))).scalars().all()
        return [{
            "id": row.id, "status": row.status, "candidates": row.candidates or [],
            "results": row.results or [], "trades_created": row.trades_created,
            "error": row.error_message, "started_at": row.started_at,
            "finished_at": row.finished_at, "created_at": row.created_at,
        } for row in rows]


@router.put("/config")
async def update_config(request: Request):
    body = await request.json()
    with SessionLocal() as db:
        config = get_config(db)
        if "enabled" in body:
            if not isinstance(body["enabled"], bool):
                raise HTTPException(400, "Invalid enabled")
            config.enabled = body["enabled"]
        if "max_candidates" in body:
            value = body["max_candidates"]
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                raise HTTPException(400, "max_candidates must be 1-5")
            config.max_candidates = value
        for field in ("quick_model", "deep_model"):
            if field in body and isinstance(body[field], str) and body[field].strip():
                setattr(config, field, body[field].strip())
        db.commit()
        return {"enabled": config.enabled, "max_candidates": config.max_candidates, "quick_model": config.quick_model, "deep_model": config.deep_model}


@router.post("/run", status_code=202)
async def queue_run():
    with SessionLocal() as db:
        config = get_config(db)
        if not config.enabled:
            raise HTTPException(503, "AI Auto Trade disabled")
        if not get_settings().ai_trading_enabled:
            raise HTTPException(503, "AI Trading disabled")
        paper = db.execute(select(PaperBotConfig).limit(1)).scalar_one_or_none()
        if not paper or not paper.enabled:
            raise HTTPException(503, "Paper Trading disabled")
        active = db.execute(select(AIAutoTradeRun).where(AIAutoTradeRun.status.in_(["QUEUED", "RUNNING"])).limit(1)).scalar_one_or_none()
        if active:
            raise HTTPException(409, f"Run {active.id} already active")
        run = AIAutoTradeRun(status="QUEUED")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    asyncio.create_task(asyncio.to_thread(execute_run, run_id))
    return {"run_id": run_id, "status": "QUEUED"}
