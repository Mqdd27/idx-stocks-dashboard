from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, select
from .batch_model import AITradingBatch
from .calendar_sync_service import calendar_fresh
from .models import CollectorLog, IntradayPrice
from .telegram_delivery_model import TelegramDelivery

def operations_health(db):
    now = datetime.now(timezone.utc)
    calendar = db.execute(select(CollectorLog).where(CollectorLog.collector == "market_calendar", CollectorLog.message == "CALENDAR_SYNC_OK").order_by(desc(CollectorLog.created_at)).limit(1)).scalar_one_or_none()
    intraday = db.execute(select(IntradayPrice).order_by(desc(IntradayPrice.timestamp)).limit(1)).scalar_one_or_none()
    batch = db.execute(select(AITradingBatch).order_by(desc(AITradingBatch.updated_at)).limit(1)).scalar_one_or_none()
    failed = db.execute(select(TelegramDelivery).where(TelegramDelivery.status == "FAILED").order_by(desc(TelegramDelivery.generated_at)).limit(10)).scalars().all()
    return {"generated_at": now, "calendar": {"fresh": calendar_fresh(), "last_sync": calendar.created_at if calendar else None, "source": (calendar.details or {}).get("source") if calendar else None}, "collector": {"last_intraday": intraday.timestamp if intraday else None, "stale": not intraday or now - intraday.timestamp > timedelta(minutes=20)}, "batch": {"id": batch.id if batch else None, "status": batch.status if batch else "NONE", "completed": batch.completed if batch else 0, "failed": batch.failed if batch else 0, "total": batch.total if batch else 0, "updated_at": batch.updated_at if batch else None}, "telegram": {"failed_count": len(failed), "failures": [{"id": row.id, "message_type": row.message_type, "target_date": row.target_date, "cycle": row.cycle, "last_error": row.last_error, "attempt_count": row.attempt_count} for row in failed]}}
