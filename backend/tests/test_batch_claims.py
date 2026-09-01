import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from app.batch_model import AITradingBatch, AITradingBatchItem
from app.batch_service import claim_next_item, complete_item, recover_stale, retry_failed
from app.db import SessionLocal

class BatchClaimTest(unittest.TestCase):
    def test_claim_recovery_and_retry(self):
        with SessionLocal() as db:
            batch=AITradingBatch(status="QUEUED",batch_size=1,total=1); db.add(batch); db.flush(); item=AITradingBatchItem(batch_id=batch.id,symbol="AUDITTEST"); db.add(item); db.commit(); bid=batch.id; iid=item.id
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                claims=list(pool.map(lambda w: claim_next_item(bid,w), ["a","b"]))
            self.assertEqual(sum(x is not None for x in claims),1)
            winner="a" if claims[0] else "b"
            self.assertTrue(complete_item(iid,winner,result={"id":1}))
            self.assertIsNone(claim_next_item(bid,"c"))
            with SessionLocal() as db:
                b=db.get(AITradingBatch,bid); b.status="QUEUED"; i=db.get(AITradingBatchItem,iid); i.status="RUNNING"; i.claimed_by="dead"; i.attempt_count=1; i.heartbeat_at=datetime.now(timezone.utc)-timedelta(hours=1); db.commit()
            with SessionLocal() as db:
                self.assertEqual(recover_stale(db,bid,datetime.now(timezone.utc)),1); db.commit()
            self.assertIsNotNone(claim_next_item(bid,"recovered"))
            with SessionLocal() as db:
                b=db.get(AITradingBatch,bid); b.status="QUEUED"; i=db.get(AITradingBatchItem,iid); i.status="FAILED"; i.attempt_count=1; db.commit(); self.assertEqual(retry_failed(db,bid),1); db.commit()
        finally:
            with SessionLocal() as db:
                db.query(AITradingBatchItem).filter_by(batch_id=bid).delete(); db.query(AITradingBatch).filter_by(id=bid).delete(); db.commit()

if __name__ == "__main__": unittest.main()
