from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select
from .batch_service import batch_snapshot, create_batch, recover_stale, retry_failed
from .batch_model import AITradingBatch, AITradingBatchItem
from .db import SessionLocal
from .config import get_settings

router = APIRouter(prefix="/api/ai-trading/batches", tags=["ai-trading-batches"])

@router.get("")
def batches():
    with SessionLocal() as db:
        rows = db.execute(select(AITradingBatch).order_by(desc(AITradingBatch.id)).limit(20)).scalars().all()
        return [batch_snapshot(row.id) for row in rows]

@router.get("/{batch_id}")
def batch_detail(batch_id: int):
    with SessionLocal() as db:
        batch = db.get(AITradingBatch, batch_id)
        if not batch:
            raise HTTPException(404, "Batch not found")
        items = db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id == batch_id).order_by(AITradingBatchItem.id)).scalars().all()
        return {**batch_snapshot(batch_id), "items": [{"id": item.id, "symbol": item.symbol, "status": item.status, "analysis_id": item.analysis_id, "attempt_count": item.attempt_count, "claimed_by": item.claimed_by, "error": item.error_message} for item in items]}

@router.post("", status_code=202)
async def start_batch(request: Request):
    if not get_settings().ai_trading_enabled:
        raise HTTPException(503, "AI trading disabled")
    try:
        body = await request.json()
    except Exception:
        body = {}
    batch_id = create_batch(body.get("batch_size", 5))
    return {"id": batch_id, "status": "QUEUED"}

@router.post("/{batch_id}/resume", status_code=202)
def resume_batch(batch_id: int):
    if not get_settings().ai_trading_enabled:
        raise HTTPException(503, "AI trading disabled")
    with SessionLocal() as db:
        batch = db.get(AITradingBatch, batch_id)
        if not batch:
            raise HTTPException(404, "Batch not found")
        recover_stale(db, batch_id, __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        retry_failed(db, batch_id)
        db.commit()
    return {"id": batch_id, "status": "QUEUED"}
