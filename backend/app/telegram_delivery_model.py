from datetime import datetime
from sqlalchemy import BigInteger, Date, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base

class TelegramDelivery(Base):
    __tablename__ = "telegram_deliveries"
    __table_args__ = (UniqueConstraint("message_type", "target_date", "cycle", name="uq_telegram_delivery_key"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_date: Mapped[Date] = mapped_column(Date, nullable=False)
    cycle: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    telegram_message_id: Mapped[str | None] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
