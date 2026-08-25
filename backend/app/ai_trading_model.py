from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base

class AITradingAnalysis(Base):
    __tablename__ = "ai_trading_analyses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False, default="NO_TRADE")
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="NO_TRADE")
    confidence: Mapped[float] = mapped_column(nullable=False, default=0)
    runtime_seconds: Mapped[float | None] = mapped_column()
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_result: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="COMPLETED")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class AITradingJob(Base):
    __tablename__ = "ai_trading_jobs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED", index=True)
    analysis_id: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
