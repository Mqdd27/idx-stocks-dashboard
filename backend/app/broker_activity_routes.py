from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import BrokerActivityDaily

router = APIRouter(prefix="/api/broker-activity", tags=["broker-activity"])


@router.get("")
def broker_activity(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    latest_date = db.execute(select(BrokerActivityDaily.trading_date).order_by(desc(BrokerActivityDaily.trading_date)).limit(1)).scalar_one_or_none()
    if not latest_date:
        return {"data": [], "trading_date": None, "data_type": "MARKET_WIDE_EOD", "source": "IDX GetBrokerSummary"}
    rows = db.execute(select(BrokerActivityDaily).where(BrokerActivityDaily.trading_date == latest_date).order_by(desc(BrokerActivityDaily.value)).limit(limit)).scalars().all()
    return {"trading_date": latest_date, "data_type": "MARKET_WIDE_EOD", "source": "IDX GetBrokerSummary", "data": [{"broker_code": row.broker_code, "broker_name": row.broker_name, "volume": row.volume, "value": float(row.value) if row.value is not None else None, "frequency": row.frequency, "source_timestamp": row.source_timestamp, "collected_at": row.collected_at} for row in rows]}
