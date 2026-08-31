from datetime import datetime, timezone
from sqlalchemy import desc, select
from .ai_trading import analyze
from .ai_trading_model import AITradingAnalysis
from .batch_model import AITradingBatch, AITradingBatchItem
from .db import SessionLocal
from .models import Company

MAX_BATCH_SIZE=10

def create_batch(batch_size=5):
    size=max(1,min(MAX_BATCH_SIZE,int(batch_size)))
    with SessionLocal() as db:
        batch=AITradingBatch(status="QUEUED",batch_size=size)
        db.add(batch); db.flush()
        symbols=db.execute(select(Company.symbol).where(Company.symbol!="IHSG").order_by(Company.symbol)).scalars().all()
        existing={x.symbol for x in db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id==batch.id)).scalars()}
        for symbol in symbols:
            if symbol not in existing: db.add(AITradingBatchItem(batch_id=batch.id,symbol=symbol))
        batch.total=len(symbols); db.commit(); db.refresh(batch)
        return batch.id

def run_batch(batch_id):
    with SessionLocal() as db:
        batch=db.get(AITradingBatch,batch_id)
        if not batch: raise ValueError("Batch not found")
        if batch.status=="COMPLETED": return snapshot(batch)
        batch.status="RUNNING"; db.commit()
        items=db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id==batch_id,AITradingBatchItem.status.in_(["QUEUED","FAILED"])).order_by(AITradingBatchItem.id).limit(batch.batch_size)).scalars().all()
    for item in items:
        started=datetime.now(timezone.utc)
        with SessionLocal() as db:
            row=db.get(AITradingBatchItem,item.id); row.status="RUNNING"; row.started_at=started; db.commit()
        try:
            result=analyze(item.symbol)
            with SessionLocal() as db:
                row=db.get(AITradingBatchItem,item.id); row.status="COMPLETED"; row.analysis_id=result.get("id"); row.result=result; row.finished_at=datetime.now(timezone.utc); db.commit()
        except Exception as exc:
            with SessionLocal() as db:
                row=db.get(AITradingBatchItem,item.id); row.status="FAILED"; row.error_message=str(exc)[:500]; row.finished_at=datetime.now(timezone.utc); db.commit()
    from .recommendation_service import import_tradingagents
    with SessionLocal() as db:
        batch=db.get(AITradingBatch,batch_id)
        total_batch=batch.total if batch else 0
    if total_batch:
        import_tradingagents(strategy="BPJS", cycle=f"batch-{batch_id}", limit=total_batch)
    with SessionLocal() as db:
        batch=db.get(AITradingBatch,batch_id)
        batch.completed=db.query(AITradingBatchItem).filter_by(batch_id=batch_id,status="COMPLETED").count()
        batch.failed=db.query(AITradingBatchItem).filter_by(batch_id=batch_id,status="FAILED").count()
        remaining=db.query(AITradingBatchItem).filter(AITradingBatchItem.batch_id==batch_id,AITradingBatchItem.status.in_(["QUEUED","RUNNING"])).count()
        batch.status="COMPLETED" if remaining==0 else "QUEUED"; db.commit()
        return snapshot(batch)

def snapshot(batch):
    return {"id":batch.id,"status":batch.status,"batch_size":batch.batch_size,"total":batch.total,"completed":batch.completed,"failed":batch.failed,"remaining":max(0,batch.total-batch.completed-batch.failed)}
