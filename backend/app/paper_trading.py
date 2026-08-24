from dataclasses import dataclass
from typing import Optional
from datetime import date


@dataclass(frozen=True)
class ExitDecision:
    reason: Optional[str]
    price: Optional[float]


def check_exit(entry_date: date, today: date, price: float, stop: float, target: float, max_holding_days: int) -> ExitDecision:
    if price <= stop:
        return ExitDecision("stop_loss", stop)
    if price >= target:
        return ExitDecision("take_profit", target)
    if (today - entry_date).days >= max_holding_days:
        return ExitDecision("time_exit", price)
    return ExitDecision(None, None)


def setup_confidence(score: float, current_price: float, entry_price: float, stop_loss: float, take_profit: float) -> float:
    if current_price <= stop_loss:
        progress = 0.0
    elif current_price >= take_profit:
        progress = 1.0
    else:
        progress = (current_price - entry_price) / (take_profit - entry_price) if take_profit > entry_price else 0.0
    return round(max(0.0, min(4.0, float(score) * (0.5 + 0.5 * progress))), 2)


def trade_metrics(trades: list) -> dict:
    profits = [float(t.pnl or 0) for t in trades if float(t.pnl or 0) > 0]
    losses = [-float(t.pnl or 0) for t in trades if float(t.pnl or 0) < 0]
    realized = sum(float(t.pnl or 0) for t in trades)
    return {
        "realized_pnl": realized,
        "win_rate": len(profits) / len(trades) if trades else 0,
        "profit_factor": sum(profits) / sum(losses) if losses else (None if not profits else float("inf")),
        "expectancy": realized / len(trades) if trades else 0,
    }























































































































































































































































































































































































@dataclass(frozen=True)
class PaperDecision:
    action: str
    score: float
    stop: Optional[float]
    target: Optional[float]
    risk_reward: float
    reason: str


def size_position(cash: float, price: float, stop: float, risk: float = .01,
                   fee: float = .0015, slippage: float = .001,
                   max_exposure: float = .5) -> int:
    if min(cash, price, risk) <= 0 or stop >= price:
        return 0
    per_share = price * (fee + slippage) + (price - stop)
    shares = min(int(cash * risk / per_share), int(cash * max_exposure / price))
    return max(0, shares // 100)


def decide(ind: dict, min_score: float = 3, min_rr: float = 2) -> PaperDecision:
    price, atr = ind.get("last_price"), ind.get("atr14")
    if not price or not atr or atr <= 0:
        return PaperDecision("no_trade", 0, None, None, 0, "insufficient price or ATR")
    score, reasons = 0, []
    if ind.get("sma20") and price > ind["sma20"]: score += 1; reasons.append("price above SMA20")
    if ind.get("sma50") and price > ind["sma50"]: score += 1; reasons.append("price above SMA50")
    if ind.get("rsi14") is not None and 50 <= ind["rsi14"] <= 70: score += 1; reasons.append("RSI confirms momentum")
    if ind.get("macd") and ind["macd"].get("histogram", 0) > 0: score += 1; reasons.append("positive MACD")
    stop = price - 1.5 * atr
    target = price + 3 * atr
    rr = (target - price) / (price - stop)
    if score < min_score or rr < min_rr:
        return PaperDecision("no_trade", score, stop, target, rr, "; ".join(reasons) or "filters not met")
    return PaperDecision("buy", score, stop, target, rr, "; ".join(reasons))
