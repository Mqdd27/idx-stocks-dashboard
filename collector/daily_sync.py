"""Daily sync collector.

- Seeds companies from seed_companies.json
- Fetches daily OHLCV history (5y) for every company incl. IHSG
- Fetches annual + quarterly fundamentals (Yahoo timeseries)
- Computes and stores financial_ratios (deterministic, backend-side)

Run manually:  python3 daily_sync.py
Runs via systemd timer (post-close + pre-open).
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.common import (  # noqa: E402
    SessionLocal,
    TZ,
    get_logger,
    log_to_db,
    now_wib,
    upsert_companies,
)
from app import models as db_models  # noqa: E402
from collector import yahoo  # noqa: E402
from collector import news as news_collector  # noqa: E402

logger = get_logger("daily_sync")


def load_seed() -> list[dict]:
    path = Path(__file__).resolve().parent / "seed_companies.json"
    return json.loads(path.read_text())


def all_symbols() -> list[tuple[str, str]]:
    """Return (symbol, yahoo_symbol) for all companies + IHSG."""
    from sqlalchemy import select

    db = SessionLocal()
    try:
        rows = db.execute(
            select(db_models.Company.symbol, db_models.Company.yahoo_symbol)
        ).all()
        return [(r[0], r[1]) for r in rows]
    finally:
        db.close()


def store_daily_rows(company_id: int, rows: list[dict]) -> int:
    from sqlalchemy import select

    db = SessionLocal()
    count = 0
    try:
        for row in rows:
            existing = db.execute(
                select(db_models.DailyPrice).where(
                    db_models.DailyPrice.company_id == company_id,
                    db_models.DailyPrice.date == row["date"],
                )
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(
                db_models.DailyPrice(
                    company_id=company_id,
                    date=row["date"],
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    previous_close=row.get("previous_close"),
                    volume=row.get("volume"),
                )
            )
            count += 1
        db.commit()
        return count
    finally:
        db.close()


def store_fundamentals(company_id: int, period_type: str, rows: list[dict]) -> int:
    from sqlalchemy import select

    db = SessionLocal()
    count = 0
    try:
        for row in rows:
            period = row["period"]
            existing = db.execute(
                select(db_models.FinancialStatement).where(
                    db_models.FinancialStatement.company_id == company_id,
                    db_models.FinancialStatement.period == period,
                    db_models.FinancialStatement.period_type == period_type,
                )
            ).scalar_one_or_none()
            if existing:
                continue
            mapped = {}
            for yahoo_field, db_field in yahoo.FUND_FIELD_MAP.items():
                if db_field in ("free_cashflow", "shares_outstanding"):
                    continue
                if yahoo_field in row:
                    mapped[db_field] = row[yahoo_field]
            if row.get("TotalAssets") is not None and row.get("StockholdersEquity") is not None:
                mapped["total_liabilities"] = row["TotalAssets"] - row["StockholdersEquity"]
            db.add(
                db_models.FinancialStatement(
                    company_id=company_id,
                    period=period,
                    period_type=period_type,
                    source="yahoo",
                    **mapped,
                )
            )
            count += 1
        db.commit()
        return count
    finally:
        db.close()


def compute_ratios(company_id: int) -> int:
    """Compute ratios from stored statements (annual, in order)."""
    from sqlalchemy import select

    db = SessionLocal()
    count = 0
    try:
        stmts = db.execute(
            select(db_models.FinancialStatement)
            .where(
                db_models.FinancialStatement.company_id == company_id,
                db_models.FinancialStatement.period_type == "annual",
            )
            .order_by(db_models.FinancialStatement.period)
        ).scalars().all()
        if len(stmts) < 2:
            return 0
        prev = stmts[-2]
        cur = stmts[-1]
        ratio = db_models.FinancialRatio(
            company_id=company_id,
            period=cur.period,
            period_type="annual",
            source="yahoo",
        )
        ratio.eps = cur.eps
        if cur.revenue:
            if cur.gross_profit is not None:
                ratio.gross_margin = round(cur.gross_profit / cur.revenue * 100, 2)
            if cur.operating_profit is not None:
                ratio.operating_margin = round(cur.operating_profit / cur.revenue * 100, 2)
            if cur.net_income is not None:
                ratio.npm = round(cur.net_income / cur.revenue * 100, 2)
        if cur.total_equity:
            if cur.net_income is not None:
                ratio.roe = round(cur.net_income / cur.total_equity * 100, 2)
            if cur.total_liabilities is not None:
                ratio.der = round(cur.total_liabilities / cur.total_equity, 2)
        if cur.total_assets and cur.net_income is not None:
            ratio.roa = round(cur.net_income / cur.total_assets * 100, 2)
        if cur.revenue and prev.revenue:
            ratio.revenue_growth = round((cur.revenue / prev.revenue - 1) * 100, 2)
        if cur.net_income is not None and prev.net_income:
            ratio.net_income_growth = round((cur.net_income / prev.net_income - 1) * 100, 2)
        existing = db.execute(
            select(db_models.FinancialRatio).where(
                db_models.FinancialRatio.company_id == company_id,
                db_models.FinancialRatio.period == cur.period,
                db_models.FinancialRatio.period_type == "annual",
            )
        ).scalar_one_or_none()
        if existing:
            for field in ("eps", "per", "pbv", "roe", "roa", "der", "npm", "gross_margin",
                          "operating_margin", "dividend_yield", "revenue_growth", "net_income_growth"):
                value = getattr(ratio, field)
                if value is not None:
                    setattr(existing, field, value)
        else:
            db.add(ratio)
        db.commit()
        count = 1
        return count
    finally:
        db.close()


def compute_valuation(company_id: int, price: float) -> None:
    """PER/PBV/dividend_yield from latest price + eps + equity per share."""
    from sqlalchemy import select

    db = SessionLocal()
    try:
        stmt = db.execute(
            select(db_models.FinancialStatement)
            .where(
                db_models.FinancialStatement.company_id == company_id,
                db_models.FinancialStatement.period_type == "annual",
            )
            .order_by(db_models.FinancialStatement.period.desc())
        ).scalars().first()
        if not stmt or not price:
            return
        ratios_row = db.execute(
            select(db_models.FinancialRatio)
            .where(
                db_models.FinancialRatio.company_id == company_id,
                db_models.FinancialRatio.period == stmt.period,
                db_models.FinancialRatio.period_type == "annual",
            )
        ).scalar_one_or_none()
        if not ratios_row:
            return
        eps = ratios_row.eps
        if eps:
            ratios_row.per = round(price / float(eps), 2)
        shares = stmt.shares_outstanding
        if not shares and stmt.net_income is not None and stmt.eps:
            shares = float(stmt.net_income) / float(stmt.eps)
        if stmt.total_equity and shares:
            bvps = float(stmt.total_equity) / float(shares)
            ratios_row.pbv = round(price / bvps, 2)
        if stmt.dividend_per_share:
            ratios_row.dividend_yield = round(float(stmt.dividend_per_share) / price * 100, 2)
        db.commit()
    finally:
        db.close()


async def sync_prices(symbols: list[tuple[str, str]]) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        for i, (symbol, yahoo_symbol) in enumerate(symbols):
            try:
                chart = await yahoo.fetch_chart(yahoo_symbol, "5y", "1d", client=client)
                if not chart:
                    continue
                rows = yahoo.chart_to_daily_rows(chart)
                company = db_get_company(symbol)
                if not company:
                    continue
                added = store_daily_rows(company.id, rows)
                meta = chart.get("meta", {})
                latest = meta.get("regularMarketPrice")
                if latest and rows:
                    compute_valuation(company.id, float(latest))
                logger.info("[%s/%s] %s: %d new daily rows", i + 1, len(symbols), symbol, added)
            except Exception as exc:  # noqa: BLE001
                logger.error("%s price sync failed: %s", symbol, exc)
                log_to_db("daily_sync", "error", f"{symbol} price sync failed: {exc}")


def db_get_company(symbol: str) -> db_models.Company | None:
    from sqlalchemy import select

    db = SessionLocal()
    try:
        return db.execute(
            select(db_models.Company).where(db_models.Company.symbol == symbol)
        ).scalar_one_or_none()
    finally:
        db.close()


_STATE_FILE = Path(__file__).resolve().parent.parent / "shared" / "fundamentals_state.json"
_STALE_AFTER_DAYS = 7


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2))


async def sync_fundamentals(symbols: list[tuple[str, str]]) -> None:
    state = _load_state()
    today = now_wib().date().isoformat()
    stale = [
        (s, y)
        for s, y in symbols
        if s != "IHSG"
        and state.get(s, "") < (now_wib().date() - timedelta(days=_STALE_AFTER_DAYS)).isoformat()
    ]
    if not stale:
        logger.info("fundamentals: all fresh, skipping (%d symbols)", len(symbols) - 1)
        return
    logger.info("fundamentals: refreshing %d symbols", len(stale))
    async with httpx.AsyncClient(timeout=60) as client:
        for i, (symbol, yahoo_symbol) in enumerate(stale):
            try:
                company = db_get_company(symbol)
                if not company:
                    continue
                annual = await yahoo.fetch_fundamentals(yahoo_symbol, yahoo.FUND_TYPES_ANNUAL, client=client)
                quarterly = await yahoo.fetch_fundamentals(yahoo_symbol, yahoo.FUND_TYPES_QUARTERLY, client=client)
                a_rows = yahoo.parse_fundamentals(annual, "annual") if annual else []
                q_rows = yahoo.parse_fundamentals(quarterly, "quarterly") if quarterly else []
                a_added = store_fundamentals(company.id, "annual", a_rows)
                q_added = store_fundamentals(company.id, "quarterly", q_rows)
                compute_ratios(company.id)
                state[symbol] = today
                _save_state(state)
                logger.info(
                    "[%s/%s] %s: %d annual + %d quarterly",
                    i + 1,
                    len(stale),
                    symbol,
                    a_added,
                    q_added,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("%s fundamentals sync failed: %s", symbol, exc)


def main() -> None:
    start = time.monotonic()
    logger.info("daily_sync start")
    log_to_db("daily_sync", "info", "start")
    upsert_companies(load_seed())
    symbols = all_symbols()
    logger.info("companies seeded: %d", len(symbols))
    asyncio.run(sync_prices(symbols))
    asyncio.run(sync_fundamentals(symbols))
    db = SessionLocal()
    try:
        from sqlalchemy import select

        name_rows = db.execute(select(db_models.Company.symbol, db_models.Company.company_name)).all()
        names = {r[0]: r[1] for r in name_rows}
    finally:
        db.close()
    asyncio.run(news_collector.sync_news(symbols, names))
    elapsed = int(time.monotonic() - start)
    logger.info("daily_sync done in %ss", elapsed)
    log_to_db("daily_sync", "info", f"done in {elapsed}s")


if __name__ == "__main__":
    main()