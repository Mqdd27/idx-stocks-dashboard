from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .db import Base


class TradeProposal(Base):
    __tablename__ = "trade_proposals"
    __table_args__ = (UniqueConstraint("recommendation_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trade_recommendations.id", ondelete="CASCADE"), nullable=False)
    analysis_id: Mapped[int | None] = mapped_column(BigInteger)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    signal: Mapped[str] = mapped_column(String(16), nullable=False)
    reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_min: Mapped[float | None] = mapped_column(Float)
    entry_max: Mapped[float | None] = mapped_column(Float)
    suggested_tp1: Mapped[float | None] = mapped_column(Float)
    suggested_tp2: Mapped[float | None] = mapped_column(Float)
    suggested_sl: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    quant_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    foreign_flow_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    market_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RiskDecision(Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (UniqueConstraint("proposal_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trade_proposals.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    max_position_value: Mapped[float] = mapped_column(Float, nullable=False)
    position_size_lots: Mapped[int] = mapped_column(BigInteger, nullable=False)
    risk_amount: Mapped[float] = mapped_column(Float, nullable=False)
    risk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    stop_price: Mapped[float | None] = mapped_column(Float)
    tp1: Mapped[float | None] = mapped_column(Float)
    tp2: Mapped[float | None] = mapped_column(Float)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float)
    portfolio_exposure_after: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TradePlan(Base):
    __tablename__ = "trade_plans"
    __table_args__ = (UniqueConstraint("proposal_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trade_proposals.id", ondelete="CASCADE"), nullable=False)
    risk_decision_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("risk_decisions.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_min: Mapped[float | None] = mapped_column(Float)
    entry_max: Mapped[float | None] = mapped_column(Float)
    position_size_lots: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tp1: Mapped[float | None] = mapped_column(Float)
    tp2: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    expected_risk: Mapped[float] = mapped_column(Float, nullable=False)
    expected_reward: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    is_shadow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    executed_trade_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("paper_trades.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
