import os
import socket
import sys
from pathlib import Path
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.batch_model import AITradingBatch
from app.batch_service import run_one_item
from app.db import SessionLocal

worker_id = f"{socket.gethostname()}:{os.getpid()}"
with SessionLocal() as db:
    batch = db.execute(select(AITradingBatch).where(AITradingBatch.status.in_(["QUEUED", "RUNNING"])).order_by(AITradingBatch.id).limit(1)).scalar_one_or_none()
if batch:
    print(run_one_item(batch.id, worker_id), flush=True)
