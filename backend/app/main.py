"""Stocks Dashboard - FastAPI backend."""
import asyncio
import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session, aliased

from . import analytics, security
from . import models as db_models
from .ai_provider import AIError, _model_kind, complete, discover_models, get_queue_status
from .config import get_settings
from .db import get_db
from .rate_limit import rate_limit
from .market_calendar import get_market_status
from .paper_trading import check_exit, decide, setup_confidence, size_position, trade_metrics

settings = get_settings()
_paper_candidates_cache: dict[tuple, tuple[float, list[dict]]] = {}

app = FastAPI(title="Stocks Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = (
    "You are an Indonesian equity research assistant.\n"
    "Use only the supplied market and financial data.\n"
    "Never invent financial numbers.\n"
    "Clearly distinguish facts from interpretation.\n"
    "If data is missing, state that it is unavailable.\n"
    "Do not issue guaranteed investment returns.\n"
    "Return structured analysis.\n"
)


def _json_dumps(obj) -> str:
    from decimal import Decimal

    return json.dumps(obj, indent=2, default=str)


def _json_safe(obj):
    """Recursively convert Decimal/other non-JSON types to JSON-safe values."""
    from decimal import Decimal

    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def _get_company(db: Session, symbol: str) -> db_models.Company:
    if not security.valid_symbol(symbol):
        raise HTTPException(400, "Invalid symbol")
    company = db.execute(
        select(db_models.Company).where(db_models.Company.symbol == symbol.upper())
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(404, f"Symbol {symbol.upper()} not found")
    return company


def _today_start_utc() -> datetime:
    from zoneinfo import ZoneInfo

    wib = datetime.now(timezone.utc).astimezone(ZoneInfo(settings.timezone))
    return datetime.combine(wib.date(), datetime.min.time()).replace(tzinfo=ZoneInfo(settings.timezone)).astimezone(timezone.utc)


def _latest_price(db: Session, company_id: int) -> Optional[dict]:
    prev = db.execute(
        select(db_models.DailyPrice)
        .where(db_models.DailyPrice.company_id == company_id)
        .order_by(desc(db_models.DailyPrice.date))
        .limit(1)
    ).scalar_one_or_none()
    intraday = db.execute(
        select(db_models.IntradayPrice)
        .where(
            db_models.IntradayPrice.company_id == company_id,
            db_models.IntradayPrice.timestamp >= _today_start_utc(),
        )
        .order_by(desc(db_models.IntradayPrice.timestamp))
        .limit(1)
    ).scalar_one_or_none()

    def _change(close: float, previous_close: float | None) -> tuple[Optional[float], Optional[float]]:
        change = (close - previous_close) if previous_close else None
        change_pct = (change / previous_close * 100) if previous_close else None
        return (round(change, 2) if change is not None else None,
                round(change_pct, 2) if change_pct is not None else None)

    if intraday:
        change, change_pct = _change(float(intraday.price), float(prev.previous_close) if prev and prev.previous_close else None)
        fresh = (datetime.now(timezone.utc) - intraday.timestamp).total_seconds() <= 900
        return {
            "date": intraday.timestamp.isoformat(),
            "open": float(intraday.open) if intraday.open is not None else None,
            "high": float(intraday.high) if intraday.high is not None else None,
            "low": float(intraday.low) if intraday.low is not None else None,
            "close": float(intraday.price) if intraday.price is not None else None,
            "previous_close": float(prev.previous_close) if prev and prev.previous_close else None,
            "volume": intraday.volume,
            "change": change,
            "change_pct": change_pct,
            "live": fresh, "is_live": fresh, "last_updated": intraday.timestamp.isoformat(), "market_status": get_market_status().get("status"), "is_stale": not fresh,
        }
    if not prev:
        return None
    change, change_pct = _change(float(prev.close), float(prev.previous_close) if prev.previous_close else None)
    return {
        "date": str(prev.date),
        "open": float(prev.open) if prev.open is not None else None,
        "high": float(prev.high) if prev.high is not None else None,
        "low": float(prev.low) if prev.low is not None else None,
        "close": float(prev.close) if prev.close is not None else None,
        "previous_close": float(prev.previous_close) if prev.previous_close is not None else None,
        "volume": prev.volume,
        "change": change,
        "change_pct": change_pct,
        "live": False, "is_live": False, "last_updated": prev.date.isoformat(), "market_status": get_market_status().get("status"), "is_stale": True,
    }


def _company_ratios(db: Session, company_id: int) -> Optional[dict]:
    row = db.execute(
        select(db_models.FinancialRatio)
        .where(db_models.FinancialRatio.company_id == company_id)
        .order_by(desc(db_models.FinancialRatio.period))
        .limit(1)
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "period": str(row.period),
        "period_type": row.period_type,
        "eps": float(row.eps) if row.eps is not None else None,
        "per": float(row.per) if row.per is not None else None,
        "pbv": float(row.pbv) if row.pbv is not None else None,
        "roe": float(row.roe) if row.roe is not None else None,
        "roa": float(row.roa) if row.roa is not None else None,
        "der": float(row.der) if row.der is not None else None,
        "npm": float(row.npm) if row.npm is not None else None,
        "gross_margin": float(row.gross_margin) if row.gross_margin is not None else None,
        "operating_margin": float(row.operating_margin) if row.operating_margin is not None else None,
        "dividend_yield": float(row.dividend_yield) if row.dividend_yield is not None else None,
        "revenue_growth": float(row.revenue_growth) if row.revenue_growth is not None else None,
        "net_income_growth": float(row.net_income_growth) if row.net_income_growth is not None else None,
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    result = {"status": "ok", "database": "ok", "nine_router": "ok", "ollama": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        result["status"] = "degraded"
        result["database"] = "error"
    import httpx

    try:
        httpx.get(f"{settings.nine_router_url}/models", timeout=5)
    except Exception:
        result["nine_router"] = "error"
    try:
        httpx.get(f"{settings.ollama_url}/api/tags", timeout=5)
    except Exception:
        result["ollama"] = "error"
    return result


@app.get("/api/stocks")
def list_stocks(
    q: str | None = Query(None, min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = select(db_models.Company).order_by(db_models.Company.symbol)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(db_models.Company.symbol.ilike(term) | db_models.Company.company_name.ilike(term))
    companies = db.execute(query.limit(limit)).scalars().all()
    out = []
    for c in companies:
        price = _latest_price(db, c.id)
        ratios = _company_ratios(db, c.id)
        out.append(
            {
                "symbol": c.symbol,
                "company_name": c.company_name,
                "sector": c.sector,
                "price": price,
                "ratios": ratios,
            }
        )
    return out


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str, db: Session = Depends(get_db)):
    company = _get_company(db, symbol)
    price = _latest_price(db, company.id)
    ratios = _company_ratios(db, company.id)
    return {
        "symbol": company.symbol,
        "company_name": company.company_name,
        "sector": company.sector,
        "subsector": company.subsector,
        "listing_date": str(company.listing_date) if company.listing_date else None,
        "website": company.website,
        "price": price,
        "ratios": ratios,
    }


@app.get("/api/stocks/{symbol}/prices")
def stock_prices(
    symbol: str,
    range: str = Query("1y", pattern="^(1d|1w|1m|3m|6m|1y|3y|5y)$"),
    interval: str = Query("1d", pattern="^(1d|1w|1m)$"),
    db: Session = Depends(get_db),
):
    company = _get_company(db, symbol)
    days = {"1d": 1, "1w": 7, "1m": 31, "3m": 92, "6m": 184, "1y": 366, "3y": 1100, "5y": 1830}[range]
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(db_models.DailyPrice)
        .where(db_models.DailyPrice.company_id == company.id, db_models.DailyPrice.date >= since)
        .order_by(db_models.DailyPrice.date)
    ).scalars().all()
    data = [
        {
            "time": r.date.isoformat(),
            "open": float(r.open) if r.open is not None else None,
            "high": float(r.high) if r.high is not None else None,
            "low": float(r.low) if r.low is not None else None,
            "close": float(r.close) if r.close is not None else None,
            "volume": r.volume,
        }
        for r in rows
    ]
    return {"symbol": company.symbol, "range": range, "interval": interval, "data": data}


@app.get("/api/stocks/{symbol}/financials")
def stock_financials(
    symbol: str,
    period_type: str = Query("annual", pattern="^(annual|quarterly)$"),
    db: Session = Depends(get_db),
):
    company = _get_company(db, symbol)
    rows = db.execute(
        select(db_models.FinancialStatement)
        .where(
            db_models.FinancialStatement.company_id == company.id,
            db_models.FinancialStatement.period_type == period_type,
        )
        .order_by(desc(db_models.FinancialStatement.period))
    ).scalars().all()
    return {
        "symbol": company.symbol,
        "period_type": period_type,
        "data": [
            {
                "period": str(r.period),
                "revenue": float(r.revenue) if r.revenue is not None else None,
                "gross_profit": float(r.gross_profit) if r.gross_profit is not None else None,
                "operating_profit": float(r.operating_profit) if r.operating_profit is not None else None,
                "net_income": float(r.net_income) if r.net_income is not None else None,
                "total_assets": float(r.total_assets) if r.total_assets is not None else None,
                "total_liabilities": float(r.total_liabilities) if r.total_liabilities is not None else None,
                "total_equity": float(r.total_equity) if r.total_equity is not None else None,
                "cash": float(r.cash) if r.cash is not None else None,
                "operating_cashflow": float(r.operating_cashflow) if r.operating_cashflow is not None else None,
                "investing_cashflow": float(r.investing_cashflow) if r.investing_cashflow is not None else None,
                "financing_cashflow": float(r.financing_cashflow) if r.financing_cashflow is not None else None,
                "capex": float(r.capex) if r.capex is not None else None,
            }
            for r in rows
        ],
    }


@app.get("/api/stocks/{symbol}/ratios")
def stock_ratios(symbol: str, db: Session = Depends(get_db)):
    company = _get_company(db, symbol)
    rows = db.execute(
        select(db_models.FinancialRatio)
        .where(db_models.FinancialRatio.company_id == company.id)
        .order_by(desc(db_models.FinancialRatio.period))
    ).scalars().all()
    return {
        "symbol": company.symbol,
        "data": [
            {
                "period": str(r.period),
                "period_type": r.period_type,
                "eps": float(r.eps) if r.eps is not None else None,
                "per": float(r.per) if r.per is not None else None,
                "pbv": float(r.pbv) if r.pbv is not None else None,
                "roe": float(r.roe) if r.roe is not None else None,
                "roa": float(r.roa) if r.roa is not None else None,
                "der": float(r.der) if r.der is not None else None,
                "npm": float(r.npm) if r.npm is not None else None,
                "gross_margin": float(r.gross_margin) if r.gross_margin is not None else None,
                "operating_margin": float(r.operating_margin) if r.operating_margin is not None else None,
                "dividend_yield": float(r.dividend_yield) if r.dividend_yield is not None else None,
                "revenue_growth": float(r.revenue_growth) if r.revenue_growth is not None else None,
                "net_income_growth": float(r.net_income_growth) if r.net_income_growth is not None else None,
            }
            for r in rows
        ],
    }


@app.get("/api/stocks/{symbol}/technicals")
def stock_technicals(symbol: str, db: Session = Depends(get_db)):
    company = _get_company(db, symbol)
    rows = db.execute(
        select(db_models.DailyPrice)
        .where(db_models.DailyPrice.company_id == company.id)
        .order_by(db_models.DailyPrice.date)
    ).scalars().all()
    if not rows:
        return {"symbol": company.symbol, "technicals": None}
    data = [
        {
            "date": r.date.isoformat(),
            "open": float(r.open) if r.open is not None else None,
            "high": float(r.high) if r.high is not None else None,
            "low": float(r.low) if r.low is not None else None,
            "close": float(r.close) if r.close is not None else None,
            "volume": r.volume,
        }
        for r in rows
    ]
    return {"symbol": company.symbol, "technicals": analytics.technical_indicators(data)}


@app.get("/api/stocks/{symbol}/news")
def stock_news(symbol: str, db: Session = Depends(get_db)):
    company = _get_company(db, symbol)
    rows = db.execute(
        select(db_models.News)
        .where(db_models.News.company_id == company.id)
        .order_by(desc(db_models.News.published_at))
        .limit(30)
    ).scalars().all()
    return {
        "symbol": company.symbol,
        "data": [
            {
                "title": n.title,
                "url": n.url,
                "source": n.source,
                "published_at": n.published_at.isoformat() if n.published_at else None,
                "summary": n.summary,
            }
            for n in rows
        ],
    }


def _market_rows(db: Session, limit: int = 10, order: str = "pct_desc"):
    """Latest price rows (intraday-first) for all companies with change computed in bulk."""
    intra_rows = db.execute(
        select(db_models.IntradayPrice)
        .where(
            db_models.IntradayPrice.timestamp >= _today_start_utc(),
        )
        .order_by(desc(db_models.IntradayPrice.timestamp))
    ).scalars().all()
    intra_latest: dict[int, db_models.IntradayPrice] = {}
    intra_vol: dict[int, float] = {}
    for r in intra_rows:
        intra_latest.setdefault(r.company_id, r)
        v = r.volume or 0
        if v > intra_vol.get(r.company_id, 0):
            intra_vol[r.company_id] = v

    sub = (
        select(
            db_models.DailyPrice.company_id,
            func.max(db_models.DailyPrice.date).label("max_date"),
        )
        .group_by(db_models.DailyPrice.company_id)
        .subquery()
    )
    latest = (
        select(db_models.DailyPrice)
        .join(sub, (db_models.DailyPrice.company_id == sub.c.company_id) & (db_models.DailyPrice.date == sub.c.max_date))
        .subquery()
    )
    latest_alias = aliased(db_models.DailyPrice, latest)
    rows = db.execute(
        select(db_models.Company, latest_alias)
        .join(latest_alias, latest_alias.company_id == db_models.Company.id)
        .where(db_models.Company.symbol != "IHSG")
    ).all()
    out = []
    for company, lp in rows:
        ir = intra_latest.get(company.id)
        prev = float(lp.previous_close) if lp.previous_close else None
        if not prev:
            continue
        if ir:
            close = float(ir.price)
            volume = intra_vol.get(company.id, ir.volume)
            date = ir.timestamp.isoformat()
        else:
            close = float(lp.close)
            volume = lp.volume
            date = str(lp.date)
        change_pct = (close - prev) / prev * 100
        out.append(
            {
                "symbol": company.symbol,
                "company_name": company.company_name,
                "close": close,
                "previous_close": prev,
                "change": round(close - prev, 2),
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "date": date,
            }
        )
    if order == "pct_desc":
        out.sort(key=lambda x: x["change_pct"], reverse=True)
    elif order == "pct_asc":
        out.sort(key=lambda x: x["change_pct"])
    elif order == "volume":
        today_iso = datetime.now(timezone.utc).astimezone().date().isoformat()
        today_rows = [r for r in out if r["date"].startswith(today_iso)]
        pool = today_rows if today_rows else out
        pool.sort(key=lambda x: x["volume"] or 0, reverse=True)
        return pool[:limit]
    return out[:limit]


@app.get("/api/market/status")
def market_status():
    return get_market_status()

@app.get("/api/market/holidays")
def market_holidays(db: Session = Depends(get_db)):
    rows = db.execute(select(db_models.MarketHoliday).where(db_models.MarketHoliday.market == "IDX").order_by(db_models.MarketHoliday.date)).scalars().all()
    return {"data": [{"date": r.date.isoformat(), "name": r.name, "holiday_type": r.holiday_type, "source": r.source, "source_url": r.source_url, "is_trading_day": r.is_trading_day, "notes": r.notes} for r in rows]}

@app.get("/api/market/calendar")
def market_calendar(start_date: date = Query(...), end_date: date = Query(...)):
    if end_date < start_date or (end_date - start_date).days > 366: raise HTTPException(400, "Invalid date range")
    from .market_calendar import get_holiday, is_trading_day
    out=[]; day=start_date
    while day <= end_date:
        h=get_holiday(day); out.append({"date":day.isoformat(),"is_trading_day":is_trading_day(day),"holiday":h.name if h else None,"holiday_type":h.holiday_type if h else None}); day += timedelta(days=1)
    return {"market":"IDX","timezone":"Asia/Jakarta","data":out}

@app.get("/api/market/events")
def market_events(start_date: date = Query(...), end_date: date = Query(...), db: Session = Depends(get_db)):
    if end_date < start_date or (end_date - start_date).days > 366:
        raise HTTPException(400, "Invalid date range")
    rows = db.execute(select(db_models.CorporateAction, db_models.Company.symbol).join(db_models.Company, db_models.Company.id == db_models.CorporateAction.company_id).where(db_models.CorporateAction.date >= start_date, db_models.CorporateAction.date <= end_date).order_by(db_models.CorporateAction.date)).all()
    return {"data": [{"symbol": symbol, "date": action.date.isoformat(), "action_type": action.action_type, "description": action.description, "source": action.source} for action, symbol in rows]}

@app.get("/api/market/overview")
def market_overview(db: Session = Depends(get_db)):
    ihsg = _get_company(db, "IHSG")
    ihsg_price = _latest_price(db, ihsg.id)
    gainers = _market_rows(db, 10, "pct_desc")
    losers = _market_rows(db, 10, "pct_asc")
    active = _market_rows(db, 10, "volume")
    all_rows = _market_rows(db, 10_000, "pct_desc")
    total_volume = sum(r["volume"] or 0 for r in all_rows)
    return {
        "ihsg": {"symbol": "IHSG", "price": ihsg_price},
        "gainers": gainers,
        "losers": losers,
        "most_active": active,
        "total_volume": total_volume,
    }


@app.get("/api/market/gainers")
def market_gainers(db: Session = Depends(get_db)):
    return {"data": _market_rows(db, 10, "pct_desc")}


@app.get("/api/market/losers")
def market_losers(db: Session = Depends(get_db)):
    return {"data": _market_rows(db, 10, "pct_asc")}


@app.get("/api/screener")
def screener(
    per_max: Optional[float] = Query(None),
    pbv_max: Optional[float] = Query(None),
    roe_min: Optional[float] = Query(None),
    roa_min: Optional[float] = Query(None),
    der_max: Optional[float] = Query(None),
    revenue_growth_min: Optional[float] = Query(None),
    net_income_growth_min: Optional[float] = Query(None),
    dividend_yield_min: Optional[float] = Query(None),
    volume_min: Optional[int] = Query(None),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    rsi_max: Optional[float] = Query(None),
    rsi_min: Optional[float] = Query(None),
    above_sma200: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    companies = db.execute(
        select(db_models.Company).where(db_models.Company.symbol != "IHSG")
    ).scalars().all()
    results = []
    for c in companies:
        price = _latest_price(db, c.id)
        ratios = _company_ratios(db, c.id)
        if not price or not ratios:
            continue
        if per_max is not None and (ratios.get("per") is None or ratios["per"] > per_max):
            continue
        if pbv_max is not None and (ratios.get("pbv") is None or ratios["pbv"] > pbv_max):
            continue
        if roe_min is not None and (ratios.get("roe") is None or ratios["roe"] < roe_min):
            continue
        if roa_min is not None and (ratios.get("roa") is None or ratios["roa"] < roa_min):
            continue
        if der_max is not None and (ratios.get("der") is None or ratios["der"] > der_max):
            continue
        if revenue_growth_min is not None and (
            ratios.get("revenue_growth") is None or ratios["revenue_growth"] < revenue_growth_min
        ):
            continue
        if net_income_growth_min is not None and (
            ratios.get("net_income_growth") is None or ratios["net_income_growth"] < net_income_growth_min
        ):
            continue
        if dividend_yield_min is not None and (
            ratios.get("dividend_yield") is None or ratios["dividend_yield"] < dividend_yield_min
        ):
            continue
        if volume_min is not None and (price.get("volume") is None or price["volume"] < volume_min):
            continue
        if price_min is not None and price["close"] is not None and price["close"] < price_min:
            continue
        if price_max is not None and price["close"] is not None and price["close"] > price_max:
            continue
        tech = _technicals_fast(db, c.id)
        if rsi_min is not None or rsi_max is not None:
            rsi = tech.get("rsi14") if tech else None
            if rsi is None:
                continue
            if rsi_min is not None and rsi < rsi_min:
                continue
            if rsi_max is not None and rsi > rsi_max:
                continue
        if above_sma200 is not None:
            above = tech.get("above_sma200") if tech else None
            if above is None or above != above_sma200:
                continue
        results.append(
            {
                "symbol": c.symbol,
                "company_name": c.company_name,
                "price": price,
                "ratios": ratios,
                "technicals": tech,
            }
        )
    results.sort(key=lambda x: x["price"]["change_pct"] or 0, reverse=True)
    return {"data": results}


def _technicals_fast(db: Session, company_id: int) -> Optional[dict]:
    rows = db.execute(
        select(db_models.DailyPrice)
        .where(db_models.DailyPrice.company_id == company_id)
        .order_by(desc(db_models.DailyPrice.date))
        .limit(250)
    ).scalars().all()
    rows = list(reversed(rows))
    if len(rows) < 2:
        return None
    data = [
        {
            "date": r.date.isoformat(),
            "open": float(r.open) if r.open is not None else None,
            "high": float(r.high) if r.high is not None else None,
            "low": float(r.low) if r.low is not None else None,
            "close": float(r.close) if r.close is not None else None,
            "volume": r.volume,
        }
        for r in rows
    ]
    return analytics.technical_indicators(data)


# ---------------------------------------------------------------------------
# AI endpoints
# ---------------------------------------------------------------------------

@app.get("/api/ai/models")
async def ai_models():
    return await discover_models()


@app.get("/api/ai/queue-status")
def ai_queue_status():
    return get_queue_status()


def _build_context(db: Session, symbol: str, for_local: bool = False) -> dict:
    company = _get_company(db, symbol)
    price = _latest_price(db, company.id)
    tech = _technicals_fast(db, company.id)
    stmt_limit = 4 if for_local else 12
    stmts = db.execute(
        select(db_models.FinancialStatement)
        .where(db_models.FinancialStatement.company_id == company.id)
        .order_by(desc(db_models.FinancialStatement.period))
        .limit(stmt_limit)
    ).scalars().all()
    statements = [
        {
            "period": str(s.period),
            "period_type": s.period_type,
            "revenue": float(s.revenue) if s.revenue is not None else None,
            "gross_profit": float(s.gross_profit) if s.gross_profit is not None else None,
            "operating_profit": float(s.operating_profit) if s.operating_profit is not None else None,
            "net_income": float(s.net_income) if s.net_income is not None else None,
            "total_assets": float(s.total_assets) if s.total_assets is not None else None,
            "total_liabilities": float(s.total_liabilities) if s.total_liabilities is not None else None,
            "total_equity": float(s.total_equity) if s.total_equity is not None else None,
            "operating_cashflow": float(s.operating_cashflow) if s.operating_cashflow is not None else None,
            "capex": float(s.capex) if s.capex is not None else None,
        }
        for s in stmts
    ]
    ratios_rows = db.execute(
        select(db_models.FinancialRatio)
        .where(db_models.FinancialRatio.company_id == company.id)
        .order_by(desc(db_models.FinancialRatio.period))
        .limit(stmt_limit)
    ).scalars().all()
    ratios = [
        {
            "period": str(r.period),
            "period_type": r.period_type,
            "eps": float(r.eps) if r.eps is not None else None,
            "per": float(r.per) if r.per is not None else None,
            "pbv": float(r.pbv) if r.pbv is not None else None,
            "roe": float(r.roe) if r.roe is not None else None,
            "roa": float(r.roa) if r.roa is not None else None,
            "der": float(r.der) if r.der is not None else None,
            "npm": float(r.npm) if r.npm is not None else None,
            "gross_margin": float(r.gross_margin) if r.gross_margin is not None else None,
            "operating_margin": float(r.operating_margin) if r.operating_margin is not None else None,
            "dividend_yield": float(r.dividend_yield) if r.dividend_yield is not None else None,
            "revenue_growth": float(r.revenue_growth) if r.revenue_growth is not None else None,
            "net_income_growth": float(r.net_income_growth) if r.net_income_growth is not None else None,
        }
        for r in ratios_rows
    ]
    actions = db.execute(
        select(db_models.CorporateAction)
        .where(db_models.CorporateAction.company_id == company.id)
        .order_by(desc(db_models.CorporateAction.date))
        .limit(10)
    ).scalars().all()
    corporate_actions = [
        {
            "date": str(a.date),
            "action_type": a.action_type,
            "description": a.description,
            "dividend": float(a.dividend) if a.dividend is not None else None,
        }
        for a in actions
    ]
    news_rows = db.execute(
        select(db_models.News)
        .where(db_models.News.company_id == company.id)
        .order_by(desc(db_models.News.published_at))
        .limit(4 if for_local else 10)
    ).scalars().all()
    news_items = [
        {
            "title": n.title,
            "source": n.source,
            "published_at": n.published_at.isoformat() if n.published_at else None,
            "summary": n.summary,
        }
        for n in news_rows
    ]
    from .market_calendar import get_market_status, previous_trading_day
    market = get_market_status()
    last_trading_day = previous_trading_day(datetime.fromisoformat(market["date"]).date()) if not market["is_trading_day"] else datetime.fromisoformat(market["date"]).date()
    return {
        "market": {"status": market["status"], "is_trading_day": market["is_trading_day"], "last_trading_day": last_trading_day.isoformat(), "price_is_live": market["is_open"]},
        "company": {
            "symbol": company.symbol,
            "company_name": company.company_name,
            "sector": company.sector,
            "subsector": company.subsector,
        },
        "price": price,
        "technicals": tech,
        "financial_statements": statements,
        "financial_ratios": ratios,
        "corporate_actions": corporate_actions,
        "news": news_items,
    }


def _check_ai_limits(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limit(f"ai:{client_ip}"):
        raise HTTPException(429, "Rate limit exceeded. Please wait a moment.")


@app.post("/api/ai/analyze")
async def ai_analyze(request: Request, db: Session = Depends(get_db)):
    _check_ai_limits(request)
    body = await request.json()
    symbol = security.sanitize_text(str(body.get("symbol", "")), 16).upper()
    model = security.sanitize_text(str(body.get("model", "")), 128)
    if not security.valid_symbol(symbol):
        raise HTTPException(400, "Invalid symbol")
    if not model:
        model = settings.default_ai_model
    company = _get_company(db, symbol)
    provider, _ = _model_kind(model)
    context = _build_context(db, symbol, for_local=(provider == "ollama"))
    data_payload = {
        "snapshot_date": datetime.now().astimezone().isoformat(),
        "data": context,
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyze this Indonesian stock using ONLY the supplied data below.\n"
                "Structured analysis required with sections:\n"
                "1. Company overview\n2. Price condition\n3. Fundamental health\n"
                "4. Growth\n5. Profitability\n6. Valuation\n7. Technical condition\n"
                "8. Recent catalysts\n9. Bull case\n10. Bear case\n11. Main risks\n"
                "12. Key metrics to monitor\n13. Conclusion\n\n"
                f"DATA:\n{_json_dumps(data_payload)}"
            ),
        },
    ]
    started = time.monotonic()
    stream = bool(body.get("stream", False))
    if stream:
        async def event_stream():
            q: asyncio.Queue = asyncio.Queue()
            accumulated: list[str] = []

            async def consume() -> None:
                try:
                    async for chunk in await complete(
                        messages, model, stream=True, request_type="analyze", symbol=symbol, max_tokens=1000
                    ):
                        await q.put(("chunk", chunk))
                    await q.put(("end", None))
                except AIError as exc:
                    await q.put(("error", exc))
                except Exception as exc:  # noqa: BLE001
                    await q.put(("error", exc))

            task = asyncio.create_task(consume())
            try:
                while True:
                    try:
                        kind, payload = await asyncio.wait_for(q.get(), timeout=20)
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
                        continue
                    if kind == "chunk":
                        accumulated.append(payload)
                        yield f"data: {json.dumps({'delta': payload})}\n\n"
                    elif kind == "end":
                        text = "".join(accumulated)
                        latency = int((time.monotonic() - started) * 1000)
                        provider, is_local = _model_kind(model)
                        if model.startswith("ollama"):
                            provider, is_local = "ollama", True
                        db.add(
                            db_models.AIAnalysis(
                                company_id=company.id,
                                symbol=symbol,
                                model=model,
                                provider=provider,
                                is_local=is_local,
                                request_type="analyze",
                                request_context=_json_safe(context),
                                response=text,
                                latency_ms=latency,
                                success=True,
                            )
                        )
                        db.commit()
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "done": True,
                                    "model": model,
                                    "provider": provider,
                                    "generated_at": datetime.now().astimezone().isoformat(),
                                }
                            )
                            + "\n\n"
                        )
                        return
                    else:
                        exc = payload
                        db.rollback()
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "error": str(exc),
                                    "provider": exc.provider if isinstance(exc, AIError) else "unknown",
                                    "model": exc.model if isinstance(exc, AIError) else model,
                                    "fallback_available": True,
                                }
                            )
                            + "\n\n"
                        )
                        return
            finally:
                task.cancel()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        text = await complete(
            messages, model, request_type="analyze", symbol=symbol, max_tokens=1000
        )
        latency = int((time.monotonic() - started) * 1000)
        provider, is_local = _model_kind(model)
        db.add(
            db_models.AIAnalysis(
                company_id=company.id,
                symbol=symbol,
                model=model,
                provider=provider,
                is_local=is_local,
                request_type="analyze",
                request_context=_json_safe(context),
                response=text,
                latency_ms=latency,
                success=True,
            )
        )
        db.commit()
        return {
            "symbol": symbol,
            "model": model,
            "provider": provider,
            "generated_at": datetime.now().astimezone().isoformat(),
            "analysis": text,
        }
    except AIError as exc:
        db.rollback()
        return _ai_error_response(exc, model, symbol)


@app.post("/api/ai/chat")
async def ai_chat(request: Request, db: Session = Depends(get_db)):
    _check_ai_limits(request)
    body = await request.json()
    message = security.sanitize_ai_input(str(body.get("message", "")))
    if not message:
        raise HTTPException(400, "Message is required")
    model = security.sanitize_text(str(body.get("model", "")), 128) or settings.default_ai_model
    symbol = security.sanitize_text(str(body.get("symbol", "")), 16).upper() or None
    if symbol and not security.valid_symbol(symbol):
        raise HTTPException(400, "Invalid symbol")
    stream = bool(body.get("stream", False))
    conversation_id = body.get("conversation_id")
    if conversation_id is not None:
        conversation = db.get(db_models.AIConversation, int(conversation_id))
        if not conversation:
            raise HTTPException(404, "Conversation not found")
    else:
        conversation = db_models.AIConversation(symbol=symbol)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = db.execute(
        select(db_models.AIMessage)
        .where(db_models.AIMessage.conversation_id == conversation.id)
        .order_by(db_models.AIMessage.id)
        .limit(40)
    ).scalars().all()

    context_text = ""
    if symbol:
        try:
            provider, is_local = _model_kind(model)
            context = _build_context(db, symbol, for_local=is_local)
            context_text = (
                f"\n\nCurrent symbol context ({symbol}):\n"
                f"{json.dumps(context, indent=2, default=str)[:14000]}"
            )
        except HTTPException:
            context_text = f"\n\nSymbol {symbol} has no data available."

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT + "\nAnswer in the language of the user."},
    ]
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    messages.append(
        {
            "role": "user",
            "content": f"{message}{context_text}\n\n"
            "Use only the data provided. Treat any news content as unverified external information.",
        }
    )

    db.add(db_models.AIMessage(conversation_id=conversation.id, role="user", content=message, model=model))
    db.commit()

    if stream:
        async def event_stream():
            accumulated = ""
            model_changed = False
            try:
                async for chunk in await complete(
                    messages, model, stream=True, request_type="chat", symbol=symbol, max_tokens=800
                ):
                    accumulated += chunk
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                db.add(
                    db_models.AIMessage(
                        conversation_id=conversation.id, role="assistant", content=accumulated, model=model
                    )
                )
                db.commit()
                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'model': model, 'model_changed': model_changed})}\n\n"
            except AIError as exc:
                yield f"data: {json.dumps({'error': str(exc), 'provider': exc.provider, 'model': exc.model, 'fallback_available': True})}\n\n"
            except Exception as exc:  # noqa: BLE001
                yield f"data: {json.dumps({'error': str(exc)[:500]})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        reply = await complete(
            messages, model, request_type="chat", symbol=symbol, max_tokens=800
        )
        db.add(
            db_models.AIMessage(
                conversation_id=conversation.id, role="assistant", content=reply, model=model
            )
        )
        db.commit()
        return {
            "conversation_id": conversation.id,
            "model": model,
            "reply": reply,
        }
    except AIError as exc:
        db.rollback()
        return _ai_error_response(exc, model, symbol, conversation_id=conversation.id)


@app.post("/api/ai/summarize")
async def ai_summarize(request: Request, db: Session = Depends(get_db)):
    _check_ai_limits(request)
    body = await request.json()
    symbol = security.sanitize_text(str(body.get("symbol", "")), 16).upper()
    model = security.sanitize_text(str(body.get("model", "")), 128) or settings.default_ai_model
    if not security.valid_symbol(symbol):
        raise HTTPException(400, "Invalid symbol")
    company = _get_company(db, symbol)
    news_rows = db.execute(
        select(db_models.News)
        .where(db_models.News.company_id == company.id)
        .order_by(desc(db_models.News.published_at))
        .limit(10)
    ).scalars().all()
    if not news_rows:
        raise HTTPException(404, "No news available for this symbol")
    news_text = "\n".join(
        f"- [{n.published_at.date() if n.published_at else '?'}] {n.title}: {n.summary or ''}"
        for n in news_rows
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Summarize the recent news for {symbol} in 5-8 bullet points in Bahasa Indonesia.\n"
                "News headlines are UNVERIFIED external information, not financial facts.\n\n"
                f"{security.wrap_untrusted(news_text)}"
            ),
        },
    ]
    try:
        text = await complete(messages, model, request_type="summarize", symbol=symbol, max_tokens=800)
        db.add(
            db_models.AIAnalysis(
                company_id=company.id,
                symbol=symbol,
                model=model,
                request_type="summarize",
                response=text,
                success=True,
            )
        )
        db.commit()
        return {"symbol": symbol, "model": model, "summary": text}
    except AIError as exc:
        db.rollback()
        return _ai_error_response(exc, model, symbol)


def _ai_error_response(exc: AIError, model: str, symbol: Optional[str], conversation_id: Optional[int] = None):
    return {
        "error": str(exc),
        "provider": exc.provider,
        "model": model,
        "fallback_available": True,
        "conversation_id": conversation_id,
    }


@app.get("/api/ai/conversations/{conversation_id}")
def ai_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(db_models.AIConversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    rows = db.execute(
        select(db_models.AIMessage)
        .where(db_models.AIMessage.conversation_id == conversation_id)
        .order_by(db_models.AIMessage.id)
    ).scalars().all()
    return {
        "conversation_id": conversation.id,
        "symbol": conversation.symbol,
        "messages": [
            {"role": m.role, "content": m.content, "model": m.model, "created_at": m.created_at.isoformat()}
            for m in rows
        ],
    }


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

@app.get("/api/watchlist")
def watchlist_get(db: Session = Depends(get_db)):
    items = db.execute(
        select(db_models.WatchlistItem).order_by(db_models.WatchlistItem.sort_order, db_models.WatchlistItem.symbol)
    ).scalars().all()
    out = []
    for item in items:
        company = db.execute(
            select(db_models.Company).where(db_models.Company.symbol == item.symbol)
        ).scalar_one_or_none()
        price = _latest_price(db, company.id) if company else None
        ratios = _company_ratios(db, company.id) if company else None
        out.append(
            {
                "symbol": item.symbol,
                "note": item.note,
                "sort_order": item.sort_order,
                "price": price,
                "ratios": ratios,
            }
        )
    return {"data": out}


@app.post("/api/watchlist")
async def watchlist_add(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    action = body.get("action", "add")
    symbol = security.sanitize_text(str(body.get("symbol", "")), 16).upper()
    if not security.valid_symbol(symbol):
        raise HTTPException(400, "Invalid symbol")
    if action == "add":
        existing = db.execute(
            select(db_models.WatchlistItem).where(db_models.WatchlistItem.symbol == symbol)
        ).scalar_one_or_none()
        if existing:
            return {"status": "exists", "symbol": symbol}
        item = db_models.WatchlistItem(
            symbol=symbol,
            note=security.sanitize_text(str(body.get("note", "")), 500) or None,
        )
        db.add(item)
        db.commit()
        return {"status": "added", "symbol": symbol}
    if action == "remove":
        items = db.execute(
            select(db_models.WatchlistItem).where(db_models.WatchlistItem.symbol == symbol)
        ).scalars().all()
        for item in items:
            db.delete(item)
        db.commit()
        return {"status": "removed", "symbol": symbol}
    raise HTTPException(400, "Invalid action")


def _paper_config(db: Session):
    config = db.execute(select(db_models.PaperBotConfig).limit(1)).scalar_one_or_none()
    if not config:
        config = db_models.PaperBotConfig()
        db.add(config)
        db.flush()
    marker = db.execute(select(db_models.PaperAuditEvent).where(db_models.PaperAuditEvent.event_type == "quantity_units_migrated").limit(1)).scalar_one_or_none()
    if not marker:
        for trade in db.execute(select(db_models.PaperTrade)).scalars():
            if trade.quantity >= 100 and trade.quantity % 100 == 0:
                trade.quantity //= 100
        db.add(db_models.PaperAuditEvent(event_type="quantity_units_migrated", payload={"unit": "lots"}))
        db.flush()
    return config


def _latest_prices(db: Session, symbols: set[str] | None = None):
    query = select(db_models.DailyPrice, db_models.Company).join(db_models.Company, db_models.Company.id == db_models.DailyPrice.company_id)
    if symbols:
        query = query.where(db_models.Company.symbol.in_(symbols))
    rows = db.execute(query.order_by(db_models.DailyPrice.date.desc())).all()
    prices = {}
    for price, company in rows:
        if (symbols is None or company.symbol in symbols) and company.symbol not in prices and price.close is not None:
            prices[company.symbol] = {"date": price.date, "price": float(price.close), "volume": price.volume, "timestamp": None, "source": "daily"}
    intra = select(db_models.IntradayPrice, db_models.Company).join(db_models.Company, db_models.Company.id == db_models.IntradayPrice.company_id).where(db_models.IntradayPrice.timestamp >= _today_start_utc())
    if symbols:
        intra = intra.where(db_models.Company.symbol.in_(symbols))
    for price, company in db.execute(intra.order_by(db_models.IntradayPrice.timestamp.desc())).all():
        if price.price is not None and (company.symbol not in prices or (prices[company.symbol].get("timestamp") or datetime.min.replace(tzinfo=timezone.utc)) < price.timestamp):
            prices[company.symbol] = {"date": price.timestamp.date(), "price": float(price.price), "volume": price.volume, "timestamp": price.timestamp, "source": "intraday"}
    return prices


def _execution_snapshot(db: Session, company_id: int, now: datetime):
    intra = db.execute(select(db_models.IntradayPrice).where(db_models.IntradayPrice.company_id == company_id, db_models.IntradayPrice.timestamp >= _today_start_utc()).order_by(desc(db_models.IntradayPrice.timestamp)).limit(1)).scalar_one_or_none()
    if intra and intra.price is not None and (now - intra.timestamp).total_seconds() <= settings.paper_max_snapshot_age_seconds:
        return {"price": float(intra.price), "volume": intra.volume, "timestamp": intra.timestamp, "date": intra.timestamp.date(), "source": "intraday"}
    daily = db.execute(select(db_models.DailyPrice).where(db_models.DailyPrice.company_id == company_id, db_models.DailyPrice.date == now.astimezone().date()).limit(1)).scalar_one_or_none()
    if daily and daily.close is not None:
        return {"price": float(daily.close), "volume": daily.volume, "timestamp": now, "date": daily.date, "source": "daily"}
    return None


def _mark_and_close(db: Session, config):
    trades = db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.status == "open")).scalars().all()
    if not trades:
        return trades, 0.0
    prices = _latest_prices(db, {t.symbol for t in trades})
    unrealized = 0.0
    for trade in trades:
        latest = prices.get(trade.symbol)
        if not latest:
            continue
        price = latest["price"]
        exit_decision = check_exit(trade.entry_date, date.today(), price, float(trade.stop_loss), float(trade.take_profit), int(config.max_holding_days))
        if exit_decision.reason:
            fill = exit_decision.price * (1 - float(config.slippage_rate))
            shares = trade.quantity * 100
            fees = (float(trade.entry_price) * shares + fill * shares) * float(config.fee_rate)
            trade.exit_price, trade.exit_date, trade.exit_timestamp, trade.status = fill, date.today(), datetime.now(timezone.utc), "closed"
            trade.fees, trade.pnl = fees, (fill - float(trade.entry_price)) * shares - fees
        else:
            unrealized += (price - float(trade.entry_price)) * trade.quantity * 100
    return trades, unrealized


@app.get("/api/paper-trading/summary")
def paper_summary(db: Session = Depends(get_db)):
    config = _paper_config(db)
    _, unrealized = _mark_and_close(db, config)
    db.commit()
    open_trades = db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.status == "open")).scalars().all()
    closed = db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.status == "closed")).scalars().all()
    metrics = trade_metrics(closed)
    exposure = sum(float(t.entry_price) * int(t.quantity) * 100 for t in open_trades)
    cash = float(config.cash) + metrics["realized_pnl"] - exposure - sum(float(t.fees or 0) for t in open_trades)
    return {"paper_only": True, "enabled": config.enabled, "cash": max(0.0, cash), "equity": max(0.0, cash + exposure + unrealized), "unrealized_pnl": unrealized, "open_positions": len(open_trades), "exposure": exposure, **metrics}


@app.get("/api/paper-trading/positions")
def paper_positions(db: Session = Depends(get_db)):
    config = _paper_config(db)
    trades = db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.status == "open")).scalars().all()
    prices = _latest_prices(db, {t.symbol for t in trades})
    data = []
    for trade in trades:
        current_price = prices.get(trade.symbol, {}).get("price")
        item = {k: v for k, v in trade.__dict__.items() if not k.startswith("_")}
        item["current_price"] = current_price
        item["unrealized_pnl"] = ((current_price - float(trade.entry_price)) * int(trade.quantity) * 100 if current_price is not None else None)
        item["unrealized_pnl_percent"] = (item["unrealized_pnl"] / (float(trade.entry_price) * int(trade.quantity) * 100) * 100 if current_price is not None else None)
        item["confidence_score"] = (setup_confidence(float(trade.score), current_price, float(trade.entry_price), float(trade.stop_loss), float(trade.take_profit)) if current_price is not None else float(trade.score))
        data.append(_json_safe(item))
    db.commit()
    return {"data": data}


@app.get("/api/paper-trading/history")
def paper_history(db: Session = Depends(get_db)):
    return {"data": [_json_safe(t.__dict__) for t in db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.status == "closed").order_by(desc(db_models.PaperTrade.exit_date))).scalars()]}


@app.get("/api/paper-trading/logs")
def paper_logs(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.execute(select(db_models.PaperAuditEvent).order_by(desc(db_models.PaperAuditEvent.created_at)).limit(limit)).scalars().all()
    return {"data": [_json_safe({k: v for k, v in row.__dict__.items() if not k.startswith("_")}) for row in rows]}


@app.get("/api/paper-trading/config")
def paper_config(db: Session = Depends(get_db)):
    config = _paper_config(db)
    db.commit()
    return _json_safe({k: v for k, v in config.__dict__.items() if not k.startswith("_")})


@app.put("/api/paper-trading/config")
async def paper_config_update(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    limits = {"cash": (0, 10**15), "risk_per_trade": (0, 1), "fee_rate": (0, 1), "slippage_rate": (0, 1), "min_score": (0, 100), "min_rr": (0, 100), "max_positions": (1, 10000), "max_exposure": (0, 1), "max_holding_days": (1, 10000)}
    config = _paper_config(db)
    for key, (low, high) in limits.items():
        if key in body:
            value = body[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= value <= high:
                raise HTTPException(400, f"Invalid {key}")
            setattr(config, key, value)
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            raise HTTPException(400, "Invalid enabled")
        config.enabled = body["enabled"]
    db.add(config)
    db.commit()
    db.refresh(config)
    _paper_candidates_cache.clear()
    return _json_safe({k: v for k, v in config.__dict__.items() if not k.startswith("_")})


@app.post("/api/paper-trading/toggle")
async def paper_toggle(request: Request, db: Session = Depends(get_db)):
    config = db.execute(select(db_models.PaperBotConfig).limit(1)).scalar_one_or_none() or db_models.PaperBotConfig()
    body = await request.json(); config.enabled = bool(body.get("enabled", not config.enabled));     db.add(config); db.add(db_models.PaperAuditEvent(event_type="toggle", payload={"enabled": config.enabled})); db.commit()
    _paper_candidates_cache.clear()
    return {"paper_only": True, "enabled": config.enabled}


@app.get("/api/paper-trading/candidates")
@app.get("/api/paper-trading/signals")
def paper_candidates(
    force: bool = Query(False),
    limit: int | None = Query(None, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    config = _paper_config(db)
    if not config.enabled and not force:
        return {"data": []}
    universe = settings.paper_universe
    candidate_limit = limit or settings.paper_candidates_limit
    cache_key = (tuple(universe), candidate_limit, float(config.min_score), float(config.min_rr))
    cached = _paper_candidates_cache.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < settings.paper_candidates_cache_seconds:
        return {"data": cached[1]}
    query = select(db_models.Company).order_by(db_models.Company.symbol)
    if universe:
        query = query.where(db_models.Company.symbol.in_(universe))
    companies = db.execute(query.limit(candidate_limit)).scalars()
    rows = []
    for company in companies:
        prices = db.execute(
            select(db_models.DailyPrice)
            .where(db_models.DailyPrice.company_id == company.id, db_models.DailyPrice.close.is_not(None))
            .order_by(db_models.DailyPrice.date.desc()).limit(settings.paper_candidates_limit)
        ).scalars().all()[::-1]
        indicators = analytics.technical_indicators([{"date": p.date, "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume} for p in prices])
        if indicators:
            decision = decide(indicators, float(config.min_score), float(config.min_rr))
            rows.append({"symbol": company.symbol, **decision.__dict__, "score_quality": "setup_score_0_4"})
    _paper_candidates_cache.clear()
    _paper_candidates_cache[cache_key] = (now, rows)
    return {"data": rows}


@app.post("/api/paper-trading/run")
def paper_run(db: Session = Depends(get_db)):
    config = _paper_config(db)
    _mark_and_close(db, config)
    if not config.enabled:
        db.commit()
        return {"status": "disabled", "created": 0}
    now = datetime.now(timezone.utc)
    run_key = now.strftime("%Y-%m-%d")
    if db.execute(select(db_models.PaperAuditEvent).where(db_models.PaperAuditEvent.event_type == "run", db_models.PaperAuditEvent.payload["run_key"].as_string() == run_key)).scalar_one_or_none(): return {"status": "already_run", "run_key": run_key}
    created = 0
    reasons = []
    open_trades = db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.status == "open")).scalars().all()
    used_cash = sum(float(t.entry_price) * t.quantity * 100 for t in open_trades)
    for item in paper_candidates(db)["data"]:
        if item["action"] != "buy" or len(open_trades) + created >= config.max_positions:
            continue
        company = db.execute(select(db_models.Company).where(db_models.Company.symbol == item["symbol"])).scalar_one()
        snapshot = _execution_snapshot(db, company.id, now)
        if not snapshot:
            reasons.append({"symbol": item["symbol"], "reason": "no current-session price snapshot"})
            continue
        price = snapshot["price"]
        historical = db.execute(select(db_models.DailyPrice).where(db_models.DailyPrice.company_id == company.id, db_models.DailyPrice.close.is_not(None)).order_by(db_models.DailyPrice.date.desc()).limit(settings.paper_candidates_limit)).scalars().all()[::-1]
        current_indicators = analytics.technical_indicators([{"date": p.date, "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume} for p in historical]) or {}
        current_indicators["last_price"] = price
        confirmation = decide(current_indicators, float(config.min_score), float(config.min_rr))
        if confirmation.action != "buy":
            reasons.append({"symbol": item["symbol"], "reason": "current snapshot failed setup confirmation"})
            continue
        duplicate = db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.symbol == item["symbol"], db_models.PaperTrade.entry_date == snapshot["date"], db_models.PaperTrade.run_key == run_key)).scalar_one_or_none()
        snapshot_key = snapshot["timestamp"].isoformat() if snapshot["timestamp"] else str(snapshot["date"])
        if duplicate or db.execute(select(db_models.PaperAuditEvent).where(db_models.PaperAuditEvent.event_type == "signal")).scalars().all() and any(e.payload.get("symbol") == item["symbol"] and e.payload.get("snapshot") == snapshot_key for e in db.execute(select(db_models.PaperAuditEvent).where(db_models.PaperAuditEvent.event_type == "signal")).scalars().all()):
            reasons.append({"symbol": item["symbol"], "reason": "duplicate signal or entry for snapshot"})
            continue
        qty = size_position(float(config.cash) - used_cash, price, item["stop"], float(config.risk_per_trade), float(config.fee_rate), float(config.slippage_rate), float(config.max_exposure))
        cost = price * qty * 100 * (1 + float(config.fee_rate) + float(config.slippage_rate))
        if qty and used_cash + cost <= float(config.cash) and db.execute(select(db_models.PaperTrade).where(db_models.PaperTrade.symbol == item["symbol"], db_models.PaperTrade.status == "open")).scalar_one_or_none() is None:
            db.add(db_models.PaperTrade(symbol=item["symbol"], entry_date=snapshot["date"], entry_timestamp=now, entry_price=price * (1 + float(config.slippage_rate)), quantity=qty, stop_loss=confirmation.stop, take_profit=confirmation.target, score=confirmation.score, reason=confirmation.reason, run_key=run_key)); db.add(db_models.PaperAuditEvent(event_type="signal", payload={"symbol": item["symbol"], "snapshot": snapshot_key, "timestamp": now.isoformat(), "action": "buy"})); created += 1; used_cash += cost
    db.add(db_models.PaperAuditEvent(event_type="run", payload={"run_key": run_key, "created": created, "reasons": reasons, "timestamp": now.isoformat()})); db.commit()
    _paper_candidates_cache.clear()
    return {"status": "ok", "run_key": run_key, "created": created}


@app.get("/api/paper-trading/trades/{trade_id}")
def paper_trade_detail(trade_id: int, db: Session = Depends(get_db)):
    trade = db.get(db_models.PaperTrade, trade_id)
    if not trade: raise HTTPException(404, "Paper trade not found")
    return _json_safe(trade.__dict__)
