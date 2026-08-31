from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .db import Base


class PaperBotConfig(Base):
    __tablename__ = "paper_bot_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(20, 2), default=100000000, nullable=False)
    risk_per_trade: Mapped[float] = mapped_column(Numeric(8, 5), default=0.01, nullable=False)
    fee_rate: Mapped[float] = mapped_column(Numeric(8, 5), default=0.0015, nullable=False)
    slippage_rate: Mapped[float] = mapped_column(Numeric(8, 5), default=0.001, nullable=False)
    min_score: Mapped[float] = mapped_column(Numeric(5, 2), default=3, nullable=False)
    min_rr: Mapped[float] = mapped_column(Numeric(5, 2), default=2, nullable=False)
    max_positions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_exposure: Mapped[float] = mapped_column(Numeric(8, 5), default=0.5, nullable=False)
    max_holding_days: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    __table_args__ = (UniqueConstraint("symbol", "entry_date"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    exit_date: Mapped[Optional[date]] = mapped_column(Date)
    exit_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False, index=True)
    entry_price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    take_profit: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    fees: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    pnl: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    run_key: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperTradeSignal(Base):
    __tablename__ = "paper_trade_signals"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    risk_reward: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    run_key: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperAuditEvent(Base):
    __tablename__ = "paper_audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperStopChange(Base):
    __tablename__ = "paper_stop_changes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("paper_trades.id", ondelete="CASCADE"), nullable=False)
    old_stop: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    new_stop: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(128))
    subsector: Mapped[Optional[str]] = mapped_column(String(128))
    listing_date: Mapped[Optional[date]] = mapped_column(Date)
    website: Mapped[Optional[str]] = mapped_column(Text)
    yahoo_symbol: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("company_id", "date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    high: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    low: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    close: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    previous_close: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    value: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    frequency: Mapped[Optional[int]] = mapped_column(BigInteger)


class IntradayPrice(Base):
    __tablename__ = "intraday_prices"
    __table_args__ = (UniqueConstraint("company_id", "timestamp", "source"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    open: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    high: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    low: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    bid: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    offer: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    bid_volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    offer_volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(32), default="yahoo")


class FinancialStatement(Base):
    __tablename__ = "financial_statements"
    __table_args__ = (UniqueConstraint("company_id", "period", "period_type", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    revenue: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    gross_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    operating_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    net_income: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    total_assets: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    total_liabilities: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    total_equity: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    cash: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    operating_cashflow: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    investing_cashflow: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    financing_cashflow: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    capex: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    eps: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    shares_outstanding: Mapped[Optional[float]] = mapped_column(Numeric(20, 0))
    dividend_per_share: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    source: Mapped[str] = mapped_column(String(32), default="yahoo")


class FinancialRatio(Base):
    __tablename__ = "financial_ratios"
    __table_args__ = (UniqueConstraint("company_id", "period", "period_type", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    eps: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    per: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    pbv: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    roe: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    roa: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    der: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    npm: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    gross_margin: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    operating_margin: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    dividend_yield: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    revenue_growth: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    net_income_growth: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    source: Mapped[str] = mapped_column(String(32), default="yahoo")


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (UniqueConstraint("company_id", "date", "action_type", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    dividend: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    split_ratio: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    rights_issue: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="idx")


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    source: Mapped[Optional[str]] = mapped_column(String(64))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)


class WatchlistItem(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("name", "symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    symbol: Mapped[Optional[str]] = mapped_column(String(16))
    model: Mapped[Optional[str]] = mapped_column(String(128))
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    request_context: Mapped[Optional[dict]] = mapped_column(JSON)
    response: Mapped[Optional[str]] = mapped_column(Text)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    model: Mapped[Optional[str]] = mapped_column(String(128))
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    is_local: Mapped[Optional[bool]] = mapped_column(Boolean)
    request_type: Mapped[Optional[str]] = mapped_column(String(32))
    symbol: Mapped[Optional[str]] = mapped_column(String(16))
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[Optional[bool]] = mapped_column(Boolean)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)


class CollectorLog(Base):
    __tablename__ = "collector_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collector: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
class MarketHoliday(Base):
    __tablename__ = "market_holidays"
    __table_args__ = (UniqueConstraint("market", "date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16), default="IDX", nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    holiday_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    is_trading_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class MarketCalendarOverride(Base):
    __tablename__ = "market_calendar_overrides"
    __table_args__ = (UniqueConstraint("market", "date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16), default="IDX", nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    is_trading_day: Mapped[bool] = mapped_column(Boolean, nullable=False)
    open_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    session_1_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    session_2_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    close_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

from .ai_trading_model import AITradingAnalysis

from .ai_auto_trade_model import AIAutoTradeConfig, AIAutoTradeRun

from .recommendation_model import TradeRecommendation

from .watchlist_model import AIWatchlist

from .batch_model import AITradingBatch, AITradingBatchItem
