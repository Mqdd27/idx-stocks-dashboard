import asyncio
from fastapi import APIRouter, HTTPException, Request
from .batch_service import create_batch, run_batch, snapshot
from .batch_model import AITradingBatch, AITradingBatchItem
from .db import SessionLocal
from .config import get_settings
from sqlalchemy import desc, select

router=APIRouter(prefix="/api/ai-trading/batches",tags=["ai-trading-batches"])

@router.get("")
def batches():
 with SessionLocal() as db:
  rows=db.execute(select(AITradingBatch).order_by(desc(AITradingBatch.id)).limit(20)).scalars().all()
  return [snapshot(x) for x in rows]

@router.get("/{batch_id}")
def batch_detail(batch_id:int):
 with SessionLocal() as db:
  batch=db.get(AITradingBatch,batch_id)
  if not batch: raise HTTPException(404,"Batch not found")
  items=db.execute(select(AITradingBatchItem).where(AITradingBatchItem.batch_id==batch_id).order_by(AITradingBatchItem.id)).scalars().all()
  return {**snapshot(batch),"items":[{"id":x.id,"symbol":x.symbol,"status":x.status,"analysis_id":x.analysis_id,"error":x.error_message} for x in items]}

@router.post("",status_code=202)
async def start_batch(request:Request):
 if not get_settings().ai_trading_enabled: raise HTTPException(503,"AI trading disabled")
 try: body=await request.json()
 except Exception: body={}
 size=body.get("batch_size",5)
 batch_id=create_batch(size)
 asyncio.create_task(asyncio.to_thread(run_batch,batch_id))
 return {"id":batch_id,"status":"QUEUED","batch_size":max(1,min(5,int(size)))}

@router.post("/{batch_id}/resume",status_code=202)
async def resume_batch(batch_id:int):
 if not get_settings().ai_trading_enabled: raise HTTPException(503,"AI trading disabled")
 with SessionLocal() as db:
  if not db.get(AITradingBatch,batch_id): raise HTTPException(404,"Batch not found")
 asyncio.create_task(asyncio.to_thread(run_batch,batch_id))
 return {"id":batch_id,"status":"QUEUED"}
