from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .db import get_db
from .risk_model import RiskDecision, TradePlan, TradeProposal
from .config import get_settings
from .risk_service import sync_shadow

router = APIRouter(prefix="/api/risk", tags=["risk"])
plans_router = APIRouter(prefix="/api/trade-plans", tags=["risk"])


def proposal_row(row):
    return {
        "id": row.id,
        "recommendation_id": row.recommendation_id,
        "analysis_id": row.analysis_id,
        "symbol": row.symbol,
        "strategy": row.strategy,
        "method": row.method,
        "signal": row.signal,
        "reference_price": row.reference_price,
        "entry_min": row.entry_min,
        "entry_max": row.entry_max,
        "suggested_tp1": row.suggested_tp1,
        "suggested_tp2": row.suggested_tp2,
        "suggested_sl": row.suggested_sl,
        "confidence": row.confidence,
        "quant_context": row.quant_context,
        "foreign_flow_context": row.foreign_flow_context,
        "market_context": row.market_context,
        "generated_at": row.generated_at,
    }


def decision_row(row):
    return {
        "id": row.id,
        "proposal_id": row.proposal_id,
        "decision": row.decision,
        "reason_codes": row.reason_codes,
        "max_position_value": row.max_position_value,
        "position_size_lots": row.position_size_lots,
        "risk_amount": row.risk_amount,
        "risk_percent": row.risk_percent,
        "stop_price": row.stop_price,
        "tp1": row.tp1,
        "tp2": row.tp2,
        "risk_reward_ratio": row.risk_reward_ratio,
        "portfolio_exposure_after": row.portfolio_exposure_after,
        "confidence_modifier": row.confidence_modifier,
        "warnings": row.warnings,
        "generated_at": row.generated_at,
    }


def plan_row(row, db):
    proposal = db.get(TradeProposal, row.proposal_id)
    decision = db.get(RiskDecision, row.risk_decision_id)
    return {
        "id": row.id,
        "proposal_id": row.proposal_id,
        "risk_decision_id": row.risk_decision_id,
        "symbol": row.symbol,
        "strategy": row.strategy,
        "method": row.method,
        "status": row.status,
        "entry_price": row.entry_price,
        "entry_min": row.entry_min,
        "entry_max": row.entry_max,
        "position_size_lots": row.position_size_lots,
        "tp1": row.tp1,
        "tp2": row.tp2,
        "stop_loss": row.stop_loss,
        "expected_risk": row.expected_risk,
        "expected_reward": row.expected_reward,
        "risk_reward_ratio": row.risk_reward_ratio,
        "valid_from": row.valid_from,
        "expires_at": row.expires_at,
        "execution_key": row.execution_key,
        "is_shadow": row.is_shadow,
        "executed_trade_id": row.executed_trade_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "notes": row.notes,
        "proposal": proposal_row(proposal) if proposal else None,
        "risk_decision": decision_row(decision) if decision else None,
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(RiskDecision.decision, func.count()).group_by(RiskDecision.decision)).all())
    return {
        "mode": "SHADOW" if get_settings().risk_shadow_mode else "DISABLED",
        "execution_enabled": False,
        "total_proposals": db.execute(select(func.count()).select_from(TradeProposal)).scalar_one(),
        "approval_count": counts.get("APPROVE", 0),
        "reduction_count": counts.get("REDUCE", 0),
        "rejection_count": counts.get("REJECT", 0),
        "generated_at": datetime.now(timezone.utc),
    }


@router.post("/sync", status_code=202)
def sync(limit: int = 100, db: Session = Depends(get_db)):
    if not get_settings().risk_shadow_mode:
        raise HTTPException(503, "Risk shadow mode disabled")
    return {"mode": "SHADOW", "created": sync_shadow(db, min(max(limit, 1), 500))}


@router.get("/proposals")
def proposals(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.execute(select(TradeProposal).order_by(desc(TradeProposal.id)).limit(min(limit, 500))).scalars().all()
    return {"data": [proposal_row(row) for row in rows]}


@router.get("/decisions")
def decisions(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.execute(
        select(RiskDecision).order_by(desc(RiskDecision.id)).limit(min(limit, 500))
    ).scalars().all()
    return {
        "data": [
            {
                **decision_row(row),
                "proposal": proposal_row(db.get(TradeProposal, row.proposal_id)),
            }
            for row in rows
        ]
    }


@router.get("/decisions/{decision_id}")
def decision(decision_id: int, db: Session = Depends(get_db)):
    row = db.get(RiskDecision, decision_id)
    if not row:
        raise HTTPException(404, "Risk decision not found")
    return decision_row(row)


@plans_router.get("")
def plans(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.execute(select(TradePlan).order_by(desc(TradePlan.id)).limit(min(limit, 500))).scalars().all()
    return {"mode": "SHADOW", "data": [plan_row(row, db) for row in rows]}


@plans_router.get("/{plan_id}")
def plan(plan_id: int, db: Session = Depends(get_db)):
    row = db.get(TradePlan, plan_id)
    if not row:
        raise HTTPException(404, "Trade plan not found")
    return plan_row(row, db)


@plans_router.post("/{plan_id}/paper-execute")
def execute_shadow_blocked(plan_id: int, db: Session = Depends(get_db)):
    row = db.get(TradePlan, plan_id)
    if not row:
        raise HTTPException(404, "Trade plan not found")
    raise HTTPException(409, "SHADOW_MODE: paper execution gate is not active")
