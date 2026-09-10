from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .db import get_db
from .foreign_flow_service import overview, ranking, stock_flow

router = APIRouter(prefix="/api/foreign-flow", tags=["foreign-flow"])


@router.get("")
def foreign_flow(period: str = Query("5d", pattern="^(1d|5d|20d|1m|3m)$"), db: Session = Depends(get_db)):
    return overview(db, period)


@router.get("/ranking")
def foreign_flow_ranking(period: str = Query("5d", pattern="^(1d|5d|20d|1m|3m)$"), direction: str = Query("buy", pattern="^(buy|sell)$"), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return {"data": ranking(db, period, direction, limit), "data_type": "VOLUME_EOD"}


@router.get("/{symbol}")
def foreign_flow_stock(symbol: str, period: str = Query("5d", pattern="^(1d|5d|20d|1m|3m)$"), db: Session = Depends(get_db)):
    return stock_flow(db, symbol, period)
