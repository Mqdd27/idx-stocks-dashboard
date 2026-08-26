from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .db import Base


class AIAutoTradeConfig(Base):
    __tablename__ = "ai_auto_trade_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_candidates: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    quick_model: Mapped[str] = mapped_column(String(128), default="cx/gpt-5.4-mini", nullable=False)
    deep_model: Mapped[str] = mapped_column(String(128), default="cx/gpt-5.5", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AIAutoTradeRun(Base):
    __tablename__ = "ai_auto_trade_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", nullable=False, index=True)
    candidates: Mapped[list | None] = mapped_column(JSON)
    results: Mapped[list | None] = mapped_column(JSON)
    trades_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
