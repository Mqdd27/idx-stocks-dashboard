from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, Float, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base

class TradeRecommendation(Base):
    __tablename__ = "trade_recommendations"
    __table_args__ = (UniqueConstraint("trading_date", "symbol", "method", "strategy", "cycle"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    cycle: Mapped[str] = mapped_column(String(32), nullable=False, default="daily")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    data_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    market_status: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_price: Mapped[float | None] = mapped_column(Float)
    entry_price: Mapped[float | None] = mapped_column(Float)
    entry_low: Mapped[float | None] = mapped_column(Float)
    entry_high: Mapped[float | None] = mapped_column(Float)
    tp1: Mapped[float | None] = mapped_column(Float)
    tp2: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    risk_reward: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    confidence_label: Mapped[str | None] = mapped_column(String(16))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reasons: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risks: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    outcome: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
