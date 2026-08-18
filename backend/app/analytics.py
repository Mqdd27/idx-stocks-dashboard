"""Deterministic analytics: technical indicators and fundamental ratios.
All calculations use pandas/numpy. No AI involved."""
import math
from typing import Optional

import numpy as np
import pandas as pd


def _series(values: list, index: list) -> pd.Series:
    return pd.Series(values, index=index, dtype="float64")


def technical_indicators(rows: list) -> Optional[dict]:
    """rows: list of dicts with date, open, high, low, close, volume (oldest first)."""
    if not rows or len(rows) < 2:
        return None
    df = pd.DataFrame(rows)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float)
    n = len(close)

    def sma(period: int) -> Optional[float]:
        return round(float(close.tail(period).mean()), 2) if n >= period else None

    def ema(period: int) -> Optional[float]:
        if n < period:
            return None
        return round(float(close.ewm(span=period, adjust=False).mean().iloc[-1]), 2)

    def rsi(period: int = 14) -> Optional[float]:
        if n < period + 1:
            return None
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        value = 100 - (100 / (1 + rs))
        v = float(value.iloc[-1])
        if math.isnan(v):
            return None
        return round(v, 2)

    def macd() -> Optional[dict]:
        if n < 26:
            return None
        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal
        return {
            "macd": round(float(macd_line.iloc[-1]), 2),
            "signal": round(float(signal.iloc[-1]), 2),
            "histogram": round(float(hist.iloc[-1]), 2),
        }

    def bollinger(period: int = 20) -> Optional[dict]:
        if n < period:
            return None
        mid = close.rolling(period).mean().iloc[-1]
        std = close.rolling(period).std().iloc[-1]
        return {
            "middle": round(float(mid), 2),
            "upper": round(float(mid + 2 * std), 2),
            "lower": round(float(mid - 2 * std), 2),
        }

    def atr(period: int = 14) -> Optional[float]:
        if n < period + 1:
            return None
        tr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return round(float(tr.rolling(period).mean().iloc[-1]), 2)

    def support_resistance() -> dict:
        window = min(n, 120)
        recent = close.iloc[-window:]
        pivot = float((high.iloc[-window:].max() + low.iloc[-window:].min() + recent.iloc[-1]) / 3)
        return {
            "support": round(float(low.iloc[-window:].min()), 2),
            "resistance": round(float(high.iloc[-window:].max()), 2),
            "pivot": round(pivot, 2),
        }

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    change = round(last_close - prev_close, 2)
    change_pct = round((change / prev_close) * 100, 2) if prev_close else None
    vol_avg_20 = round(float(vol.tail(20).mean()), 0) if n >= 20 else None

    result = {
        "last_price": last_close,
        "previous_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "high_52w": round(float(high.tail(252).max()), 2) if n >= 1 else None,
        "low_52w": round(float(low.tail(252).min()), 2) if n >= 1 else None,
        "sma5": sma(5),
        "sma10": sma(10),
        "sma20": sma(20),
        "sma50": sma(50),
        "sma100": sma(100),
        "sma200": sma(200),
        "ema12": ema(12),
        "ema26": ema(26),
        "rsi14": rsi(14),
        "macd": macd(),
        "bollinger": bollinger(20),
        "atr14": atr(14),
        "volume_avg_20": vol_avg_20,
        "support_resistance": support_resistance(),
        "above_sma200": bool(last_close > float(close.tail(200).mean())) if n >= 200 else None,
    }
    return result


def compute_fundamentals(stmts: list) -> list:
    """Compute ratios from financial statements rows (annual preferred).
    stmts: list of dicts: period, period_type, revenue, gross_profit, operating_profit,
    net_income, total_assets, total_liabilities, total_equity, cash,
    operating_cashflow, investing_cashflow, financing_cashflow, capex.
    Returns list of ratio dicts."""
    ratios = []
    for i, s in enumerate(stmts):
        r = {
            "period": str(s.get("period")),
            "period_type": s.get("period_type"),
            "eps": None,
            "per": None,
            "pbv": None,
            "roe": None,
            "roa": None,
            "der": None,
            "npm": None,
            "gross_margin": None,
            "operating_margin": None,
            "dividend_yield": None,
            "revenue_growth": None,
            "net_income_growth": None,
        }
        rev = s.get("revenue")
        gp = s.get("gross_profit")
        op = s.get("operating_profit")
        ni = s.get("net_income")
        ta = s.get("total_assets")
        tl = s.get("total_liabilities")
        te = s.get("total_equity")
        if gp is not None and rev:
            r["gross_margin"] = round(gp / rev * 100, 2)
        if op is not None and rev:
            r["operating_margin"] = round(op / rev * 100, 2)
        if ni is not None and rev:
            r["npm"] = round(ni / rev * 100, 2)
        if te:
            if ni is not None:
                r["roe"] = round(ni / te * 100, 2)
            if tl is not None:
                r["der"] = round(tl / te, 2)
        if ta:
            if ni is not None:
                r["roa"] = round(ni / ta * 100, 2)
        if i > 0:
            prev = stmts[i - 1]
            prev_rev = prev.get("revenue")
            prev_ni = prev.get("net_income")
            if rev and prev_rev:
                r["revenue_growth"] = round((rev / prev_rev - 1) * 100, 2)
            if ni is not None and prev_ni:
                r["net_income_growth"] = round((ni / prev_ni - 1) * 100, 2)
        ratios.append(r)
    return ratios


def cagr(start: float, end: float, years: float) -> Optional[float]:
    if not start or not end or not years or start <= 0 or end <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 2)


def free_cash_flow(s: dict) -> Optional[float]:
    ocf = s.get("operating_cashflow")
    capex = s.get("capex")
    if ocf is None or capex is None:
        if ocf is not None and s.get("investing_cashflow") is not None:
            return round(ocf + s.get("investing_cashflow"), 2)
        return None
    return round(ocf - capex, 2)