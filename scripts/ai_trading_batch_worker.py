import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.batch_model import AITradingBatch
from app.batch_service import run_batch
from app.db import SessionLocal
from sqlalchemy import desc, select

with SessionLocal() as db:
 batch=db.execute(select(AITradingBatch).where(AITradingBatch.status.in_(["QUEUED","RUNNING"])).order_by(desc(AITradingBatch.id)).limit(1)).scalar_one_or_none()
if batch:
 print(run_batch(batch.id),flush=True)
