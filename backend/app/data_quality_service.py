from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .models import CollectorLog, FinancialRatio, IntradayPrice, News

PRICE_MAX_AGE = timedelta(minutes=20)
NEWS_MAX_AGE = timedelta(days=7)
RATIOS_MAX_AGE = timedelta(days=180)


def _status(timestamp, max_age, now):
    return {
        "last_updated": timestamp,
        "max_age_seconds": int(max_age.total_seconds()),
        "stale": timestamp is None or now - timestamp > max_age,
    }


def data_quality(db: Session, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    price = db.execute(select(IntradayPrice.timestamp).order_by(desc(IntradayPrice.timestamp)).limit(1)).scalar_one_or_none()
    news = db.execute(select(News.published_at).where(News.published_at.is_not(None)).order_by(desc(News.published_at)).limit(1)).scalar_one_or_none()
    ratio_date = db.execute(select(FinancialRatio.period).order_by(desc(FinancialRatio.period)).limit(1)).scalar_one_or_none()
    collector = db.execute(select(CollectorLog.created_at).where(CollectorLog.collector == "intraday").order_by(desc(CollectorLog.created_at)).limit(1)).scalar_one_or_none()
    ratio = datetime.combine(ratio_date, datetime.min.time(), tzinfo=timezone.utc) if ratio_date else None
    return {
        "price": _status(price, PRICE_MAX_AGE, now),
        "news": _status(news, NEWS_MAX_AGE, now),
        "ratios": _status(ratio, RATIOS_MAX_AGE, now),
        "collector": _status(collector or price, PRICE_MAX_AGE, now),
    }


def critical_data_stale(db: Session, market: dict, now: datetime | None = None) -> bool:
    quality = data_quality(db, now)
    return bool(market.get("is_open") and (quality["price"]["stale"] or quality["collector"]["stale"]))
