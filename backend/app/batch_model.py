from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base

class AITradingBatch(Base):
    __tablename__ = "ai_trading_batches"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", nullable=False, index=True)
    batch_size: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class AITradingBatchItem(Base):
    __tablename__ = "ai_trading_batch_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", nullable=False, index=True)
    analysis_id: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
