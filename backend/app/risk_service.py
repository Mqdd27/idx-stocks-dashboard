from datetime import datetime, timezone

from sqlalchemy import desc, select

from .foreign_flow_service import stock_flow
from .models import PaperBotConfig, PaperTrade
from .paper_trading import size_position
from .risk_model import RiskDecision, TradePlan, TradeProposal
from .recommendation_model import TradeRecommendation

REJECT = "REJECT"
REDUCE = "REDUCE"
APPROVE = "APPROVE"


def _paper_config(db):
    config = db.execute(select(PaperBotConfig).limit(1)).scalar_one_or_none()
    if config is None:
        config = PaperBotConfig()
        db.add(config)
        db.flush()
    return config


def _analysis_id(db, recommendation):
    if recommendation.method != "TRADING_AGENTS":
        return None
    from .ai_trading_model import AITradingAnalysis

    row = db.execute(
        select(AITradingAnalysis.id)
        .where(
            AITradingAnalysis.symbol == recommendation.symbol,
            AITradingAnalysis.analysis_date == recommendation.trading_date,
        )
        .order_by(desc(AITradingAnalysis.id))
        .limit(1)
    ).scalar_one_or_none()
    return row


def _portfolio(db, config):
    open_trades = db.execute(
        select(PaperTrade).where(PaperTrade.status == "open")
    ).scalars().all()
    exposure = sum(float(trade.entry_price) * int(trade.quantity) * 100 for trade in open_trades)
    return open_trades, exposure, max(0.0, float(config.cash) - exposure)


def _proposal_context(db, recommendation):
    flow = stock_flow(db, recommendation.symbol, "5d").get("data") or {}
    return {
        "quant_context": {
            "score": recommendation.score,
            "risk_reward": recommendation.risk_reward,
            "signals": recommendation.signals or {},
            "risks": recommendation.risks or {},
        },
        "foreign_flow_context": {
            "data_type": "VOLUME_EOD",
            "net_foreign_volume": flow.get("net_foreign_volume"),
            "streak": flow.get("streak"),
            "status": flow.get("status"),
            "trading_date": str(flow["trading_date"]) if flow.get("trading_date") else None,
        },
        "market_context": {
            "market_status": recommendation.market_status,
            "data_timestamp": recommendation.data_timestamp.isoformat() if recommendation.data_timestamp else None,
        },
    }


def create_shadow_records(db, recommendation):
    proposal = db.execute(
        select(TradeProposal).where(TradeProposal.recommendation_id == recommendation.id)
    ).scalar_one_or_none()
    if proposal:
        return proposal, db.execute(
            select(RiskDecision).where(RiskDecision.proposal_id == proposal.id)
        ).scalar_one_or_none(), db.execute(
            select(TradePlan).where(TradePlan.proposal_id == proposal.id)
        ).scalar_one_or_none()

    reference = float(recommendation.current_price or recommendation.entry_price or 0)
    context = _proposal_context(db, recommendation)
    proposal = TradeProposal(
        recommendation_id=recommendation.id,
        analysis_id=_analysis_id(db, recommendation),
        symbol=recommendation.symbol,
        strategy=recommendation.strategy,
        method=recommendation.method,
        signal=recommendation.action,
        reference_price=reference,
        entry_min=recommendation.entry_low,
        entry_max=recommendation.entry_high,
        suggested_tp1=recommendation.tp1,
        suggested_tp2=recommendation.tp2,
        suggested_sl=recommendation.stop_loss,
        confidence=recommendation.score,
        **context,
    )
    db.add(proposal)
    db.flush()
    decision = evaluate(db, proposal, recommendation)
    db.add(decision)
    db.flush()
    plan = create_plan(proposal, decision, recommendation)
    if plan:
        db.add(plan)
    return proposal, decision, plan


def evaluate(db, proposal, recommendation):
    config = _paper_config(db)
    open_trades, exposure, available_cash = _portfolio(db, config)
    codes, warnings = [], []
    entry = float(proposal.reference_price or 0)
    stop = float(proposal.suggested_sl or 0)
    tp1 = float(proposal.suggested_tp1 or 0)
    tp2 = float(proposal.suggested_tp2 or 0)
    rr = float(recommendation.risk_reward or 0)
    now = datetime.now(timezone.utc)

    if proposal.signal != "BUY":
        codes.append("SIGNAL_NOT_BUY")
    if entry <= 0 or stop <= 0 or stop >= entry:
        codes.append("INVALID_STOP")
    if rr < float(config.min_rr):
        codes.append("RISK_REWARD_TOO_LOW")
    if recommendation.valid_until and recommendation.valid_until < now:
        codes.append("EXPIRED_PLAN")
    if recommendation.data_timestamp and (now - recommendation.data_timestamp).total_seconds() > 900:
        codes.append("STALE_DATA")
    if any(trade.symbol == proposal.symbol for trade in open_trades):
        codes.append("DUPLICATE_EXPOSURE")
    if len(open_trades) >= int(config.max_positions):
        codes.append("MAX_OPEN_POSITIONS")

    risk_lots = size_position(
        available_cash,
        entry,
        stop,
        float(config.risk_per_trade),
        float(config.fee_rate),
        float(config.slippage_rate),
        1.0,
    ) if not codes else 0
    lots = size_position(
        available_cash,
        entry,
        stop,
        float(config.risk_per_trade),
        float(config.fee_rate),
        float(config.slippage_rate),
        float(config.max_exposure),
    ) if not codes else 0
    if lots and risk_lots > lots:
        codes.append("POSITION_LIMIT_REDUCED")
    value = entry * lots * 100
    risk_amount = max(0.0, (entry - stop) * lots * 100) if lots else 0.0
    exposure_after = exposure + value
    max_total = float(config.cash) * float(config.max_exposure)
    if lots <= 0 and not codes:
        codes.append("POSITION_SIZE_ZERO")
    if exposure_after > max_total:
        codes.append("MAX_TOTAL_EXPOSURE")

    hard_reject = {"SIGNAL_NOT_BUY", "INVALID_STOP", "RISK_REWARD_TOO_LOW", "EXPIRED_PLAN", "STALE_DATA", "DUPLICATE_EXPOSURE", "MAX_OPEN_POSITIONS", "POSITION_SIZE_ZERO", "MAX_TOTAL_EXPOSURE"}
    decision = REJECT if any(code in hard_reject for code in codes) else (REDUCE if "POSITION_LIMIT_REDUCED" in codes else APPROVE)
    if proposal.foreign_flow_context.get("status") == "STRONG DISTRIBUTION":
        warnings.append("FOREIGN_FLOW_DISTRIBUTION")
    if recommendation.strategy == "BPJS":
        warnings.append("BPJS_SAME_SESSION_REQUIRED")

    return RiskDecision(
        proposal_id=proposal.id,
        decision=decision,
        reason_codes=codes,
        max_position_value=max(0.0, min(max_total - exposure, available_cash * float(config.max_exposure))),
        position_size_lots=lots,
        risk_amount=risk_amount,
        risk_percent=(risk_amount / float(config.cash)) if config.cash else 0.0,
        stop_price=stop or None,
        tp1=tp1 or None,
        tp2=tp2 or None,
        risk_reward_ratio=rr or None,
        portfolio_exposure_after=exposure_after,
        confidence_modifier=1.0,
        warnings=warnings,
    )


def create_plan(proposal, decision, recommendation):
    if decision.decision == REJECT:
        return None
    entry = proposal.reference_price
    reward = max(0.0, (float(proposal.suggested_tp1 or entry) - entry) * decision.position_size_lots * 100)
    return TradePlan(
        proposal_id=proposal.id,
        risk_decision_id=decision.id,
        symbol=proposal.symbol,
        strategy=proposal.strategy,
        method=proposal.method,
        status="PENDING",
        entry_price=entry,
        entry_min=proposal.entry_min,
        entry_max=proposal.entry_max,
        position_size_lots=decision.position_size_lots,
        tp1=proposal.suggested_tp1,
        tp2=proposal.suggested_tp2,
        stop_loss=decision.stop_price,
        expected_risk=decision.risk_amount,
        expected_reward=reward,
        risk_reward_ratio=decision.risk_reward_ratio,
        valid_from=datetime.now(timezone.utc),
        expires_at=recommendation.valid_until,
        execution_key=f"recommendation:{proposal.recommendation_id}",
        is_shadow=True,
        notes="SHADOW_MODE",
    )


def sync_shadow(db, limit=100):
    rows = db.execute(
        select(TradeRecommendation)
        .where(TradeRecommendation.action == "BUY")
        .order_by(desc(TradeRecommendation.generated_at))
        .limit(limit)
    ).scalars().all()
    created = 0
    for recommendation in rows:
        existing = db.execute(
            select(TradeProposal.id).where(TradeProposal.recommendation_id == recommendation.id)
        ).scalar_one_or_none()
        if existing:
            continue
        create_shadow_records(db, recommendation)
        created += 1
    db.commit()
    return created
