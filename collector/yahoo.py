"""Yahoo Finance data client (chart API + fundamentals timeseries API).

Structured JSON endpoints only. Browser-like User-Agent is required by Yahoo.
Rate-limit aware: sequential with backoff on 429.
"""
import asyncio
import time
from typing import Any

import httpx

from shared.common import YAHOO_HEADERS, get_logger

logger = get_logger("yahoo")

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FUND_URL = "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"

FUND_TYPES_ANNUAL = [
    "annualTotalRevenue",
    "annualGrossProfit",
    "annualOperatingIncome",
    "annualNetIncome",
    "annualTotalAssets",
    "annualStockholdersEquity",
    "annualCashAndCashEquivalents",
    "annualOperatingCashFlow",
    "annualInvestingCashFlow",
    "annualFinancingCashFlow",
    "annualCapitalExpenditure",
    "annualDilutedEPS",
    "annualDividendPerShare",
]
FUND_TYPES_QUARTERLY = [
    "quarterlyTotalRevenue",
    "quarterlyNetIncome",
]

_MAX_RETRIES = 4


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    for attempt in range(_MAX_RETRIES):
        resp = await client.get(url, params=params, headers=YAHOO_HEADERS)
        if resp.status_code == 429:
            wait = 2 ** attempt * 2
            logger.warning("Yahoo rate limit (429), waiting %ss (%s)", wait, url.split("?")[0])
            await asyncio.sleep(wait)
            continue
        if resp.status_code == 404:
            raise ValueError(f"Symbol not found: {url}")
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Yahoo rate limited persistently for {url}")


async def fetch_chart(
    yahoo_symbol: str,
    range_: str = "1y",
    interval: str = "1d",
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Return chart result dict or None."""
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        data = await _get(
            client,
            CHART_URL.format(symbol=yahoo_symbol),
            params={"range": range_, "interval": interval, "includePrePost": "false"},
        )
        result = data.get("chart", {}).get("result")
        if not result:
            return None
        return result[0]
    finally:
        if own_client:
            await client.aclose()


def chart_to_daily_rows(chart: dict) -> list[dict]:
    """Convert chart result to daily price rows (date, OHLCV)."""
    ts = chart.get("timestamp") or []
    q = chart.get("indicators", {}).get("quote", [{}])[0]
    rows = []
    prev_close = None
    for i, t in enumerate(ts):
        close = q.get("close", [])[i]
        if close is None:
            continue
        row = {
            "date": time.strftime("%Y-%m-%d", time.gmtime(t)),
            "open": q.get("open", [])[i],
            "high": q.get("high", [])[i],
            "low": q.get("low", [])[i],
            "close": close,
            "volume": q.get("volume", [])[i] or 0,
            "previous_close": prev_close,
        }
        rows.append(row)
        prev_close = close
    return rows


def chart_to_intraday_rows(chart: dict, source: str = "yahoo") -> list[dict]:
    ts = chart.get("timestamp") or []
    q = chart.get("indicators", {}).get("quote", [{}])[0]
    rows = []
    for i, t in enumerate(ts):
        close = q.get("close", [])[i]
        if close is None:
            continue
        rows.append(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + "Z",
                "price": close,
                "open": q.get("open", [])[i],
                "high": q.get("high", [])[i],
                "low": q.get("low", [])[i],
                "volume": q.get("volume", [])[i] or 0,
                "source": source,
            }
        )
    return rows


async def fetch_fundamentals(
    yahoo_symbol: str, types: list[str], client: httpx.AsyncClient | None = None
) -> dict | None:
    """Fetch fundamentals for multiple types.

    The timeseries API returns only ONE type per request, so each type is
    fetched separately (bounded concurrency) and merged.
    """
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    sem = asyncio.Semaphore(6)
    merged: dict = {"meta": {"symbol": [yahoo_symbol]}, "timestamp": [], **{t: [] for t in types}}

    async def fetch_one(t: str) -> None:
        async with sem:
            data = await _get(
                client,
                FUND_URL.format(symbol=yahoo_symbol),
                params={"symbol": yahoo_symbol, "type": t, "period1": "0", "period2": str(int(time.time()))},
            )
            result = data.get("timeseries", {}).get("result")
            if not result:
                return
            merged[t] = result[0].get(t) or []

    try:
        await asyncio.gather(*(fetch_one(t) for t in types))
        if all(not merged[t] for t in types):
            return None
        return merged
    finally:
        if own_client:
            await client.aclose()


def parse_fundamentals(result: dict, prefix: str) -> list[dict]:
    """Extract per-period values from timeseries result.
    prefix: 'annual' or 'quarterly'."""
    series_map: dict[str, list[dict]] = {}
    for key in result:
        if not key.startswith(prefix):
            continue
        series_map[key] = result[key] or []
    if not series_map:
        return []
    period_dates: dict[str, dict] = {}
    for key, series in series_map.items():
        field = key[len(prefix):]
        for item in series:
            if not item:
                continue
            as_of = item.get("asOfDate")
            if not as_of:
                continue
            raw = item.get("reportedValue", {}).get("raw")
            period_dates.setdefault(as_of, {})[field] = raw
    rows = []
    for as_of, values in sorted(period_dates.items()):
        row = {"period": as_of, **values}
        rows.append(row)
    return rows


FUND_FIELD_MAP = {
    "TotalRevenue": "revenue",
    "GrossProfit": "gross_profit",
    "OperatingIncome": "operating_profit",
    "NetIncome": "net_income",
    "TotalAssets": "total_assets",
    "TotalLiabilities": "total_liabilities",
    "StockholdersEquity": "total_equity",
    "CashAndCashEquivalents": "cash",
    "OperatingCashFlow": "operating_cashflow",
    "InvestingCashFlow": "investing_cashflow",
    "FinancingCashFlow": "financing_cashflow",
    "CapitalExpenditure": "capex",
    "FreeCashFlow": "free_cashflow",
    "DilutedEPS": "eps",
    "DividendPerShare": "dividend_per_share",
    "SharesOutstanding": "shares_outstanding",
}