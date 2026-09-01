import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from .ai_trading import analyze
from .batch_model import AITradingBatch, AITradingBatchItem
from .config import get_settings
from .db import SessionLocal
from .models import Company

MAX_BATCH_SIZE = 10
STALE_SECONDS = int(os.environ.get("AI_TRADING_BATCH_STALE_SECONDS", "900"))
MAX_ATTEMPTS = int(os.environ.get("AI_TRADING_BATCH_MAX_ATTEMPTS", "3"))


def create_batch(batch_size=5):
    size = max(1, min(MAX_BATCH_SIZE, int(batch_size)))
    with SessionLocal() as db:
        batch = AITradingBatch(status="QUEUED", batch_size=size)
        db.add(batch)
        db.flush()
        symbols = db.execute(select(Company.symbol).where(Company.symbol != "IHSG").order_by(Company.symbol)).scalars().all()
        db.add_all([AITradingBatchItem(batch_id=batch.id, symbol=symbol) for symbol in symbols])
        batch.total = len(symbols)
        db.commit()
        return batch.id


def recover_stale(db, batch_id, now):
    stale_before = now - timedelta(seconds=STALE_SECONDS)
    rows = db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id == batch_id, AITradingBatchItem.status == "RUNNING", AITradingBatchItem.heartbeat_at < stale_before).with_for_update(skip_locked=True)).scalars().all()
    for item in rows:
        if item.attempt_count >= MAX_ATTEMPTS:
            item.status = "FAILED"
            item.error_message = "STALE_MAX_ATTEMPTS"
            item.finished_at = now
        else:
            item.status = "QUEUED"
            item.claimed_by = None
            item.claimed_at = None
            item.heartbeat_at = None
            item.error_message = "STALE_RECOVERED"
    return len(rows)



def retry_failed(db, batch_id):
    rows = db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id == batch_id, AITradingBatchItem.status == "FAILED", AITradingBatchItem.attempt_count < MAX_ATTEMPTS).with_for_update(skip_locked=True)).scalars().all()
    for item in rows:
        item.status = "QUEUED"
        item.error_message = "RETRY_REQUESTED"
        item.claimed_by = None
        item.claimed_at = None
        item.heartbeat_at = None
    return len(rows)

def claim_next_item(batch_id, worker_id):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        batch = db.execute(select(AITradingBatch).where(AITradingBatch.id == batch_id).with_for_update()).scalar_one_or_none()
        if not batch or batch.status == "COMPLETED":
            return None
        recover_stale(db, batch_id, now)
        item = db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id == batch_id, AITradingBatchItem.status == "QUEUED", AITradingBatchItem.attempt_count < MAX_ATTEMPTS).order_by(AITradingBatchItem.id).with_for_update(skip_locked=True).limit(1)).scalar_one_or_none()
        if not item:
            _refresh_batch(db, batch, now)
            db.commit()
            return None
        item.status = "RUNNING"
        item.attempt_count += 1
        item.claimed_by = worker_id
        item.claimed_at = now
        item.heartbeat_at = now
        item.started_at = now
        batch.status = "RUNNING"
        db.commit()
        return {"id": item.id, "symbol": item.symbol}


def complete_item(item_id, worker_id, result=None, error=None):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        item = db.execute(select(AITradingBatchItem).where(AITradingBatchItem.id == item_id, AITradingBatchItem.claimed_by == worker_id, AITradingBatchItem.status == "RUNNING").with_for_update()).scalar_one_or_none()
        if not item:
            return False
        item.finished_at = now
        item.heartbeat_at = now
        if error:
            item.status = "FAILED" if item.attempt_count >= MAX_ATTEMPTS else "QUEUED"
            item.error_message = str(error)[:500]
            if item.status == "QUEUED":
                item.claimed_by = None
                item.claimed_at = None
        else:
            item.status = "COMPLETED"
            item.analysis_id = result.get("id") if result else None
            item.result = result
        db.flush()
        batch = db.execute(select(AITradingBatch).where(AITradingBatch.id == item.batch_id).with_for_update()).scalar_one()
        _refresh_batch(db, batch, now)
        db.commit()
        return True


def _refresh_batch(db, batch, now):
    db.flush()
    counts = dict(db.execute(select(AITradingBatchItem.status, func.count()).where(AITradingBatchItem.batch_id == batch.id).group_by(AITradingBatchItem.status)).all())
    batch.completed = counts.get("COMPLETED", 0)
    batch.failed = counts.get("FAILED", 0)
    batch.status = "COMPLETED" if batch.completed + batch.failed >= batch.total else "QUEUED"
    batch.updated_at = now


def run_one_item(batch_id, worker_id):
    if not get_settings().ai_trading_enabled:
        return {"status": "DISABLED"}
    claim = claim_next_item(batch_id, worker_id)
    if not claim:
        return batch_snapshot(batch_id)
    try:
        result = analyze(claim["symbol"])
        complete_item(claim["id"], worker_id, result=result)
    except Exception as exc:
        complete_item(claim["id"], worker_id, error=exc)
    return batch_snapshot(batch_id)


def batch_snapshot(batch_id):
    with SessionLocal() as db:
        batch = db.get(AITradingBatch, batch_id)
        if not batch:
            return None
        return {"id": batch.id, "status": batch.status, "batch_size": batch.batch_size, "total": batch.total, "completed": batch.completed, "failed": batch.failed, "remaining": max(0, batch.total - batch.completed - batch.failed)}
