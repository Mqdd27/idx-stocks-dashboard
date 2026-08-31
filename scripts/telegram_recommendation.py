from datetime import datetime
from pathlib import Path
import subprocess
from sqlalchemy import desc, select

from app.db import SessionLocal
from app.market_calendar import TZ, get_market_status, next_trading_day
from app.recommendation_model import TradeRecommendation
from app.watchlist_model import AIWatchlist


def _price(value):
    return "-" if value is None else f"{round(float(value)):,}"


def _latest(rows):
    result = {}
    for row in rows:
        result.setdefault(row.symbol, row)
    return list(result.values())


def _pick_lines(rows, ai=False):
    if not rows:
        return ["NO QUALIFIED SETUP"]
    lines = []
    for index, row in enumerate(rows[:3], 1):
        lines.extend([
            f"{index}. {row.symbol}",
            f"Entry: {_price(row.entry_low)}–{_price(row.entry_high)}",
            f"TP1: {_price(row.tp1)}",
            f"TP2: {_price(row.tp2)}",
            f"SL: {_price(row.stop_loss)}",
            f"R/R: {float(row.risk_reward or 0):.2f}",
            f"{'Confidence' if ai else 'Quant Score'}: {row.confidence_label or '-'}" if ai else f"Quant Score: {row.score or '-'}",
        ])
        if not ai:
            positives = (row.reasons or {}).get("positive") or []
            risks = (row.reasons or {}).get("negative") or (row.risks or {}).get("items") or []
            if positives:
                lines.append("Why:")
                lines.extend(f"• {reason}" for reason in positives[:4])
            if risks:
                lines.append("Risk:")
                lines.extend(f"• {risk}" for risk in risks[:3])
        lines.append("")
    return lines


def build_report(strategy, now=None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    target = next_trading_day(now.date()) if strategy == "BSJP" or now.hour >= 16 else now.date()
    with SessionLocal() as db:
        recs = db.execute(select(TradeRecommendation).where(TradeRecommendation.strategy == strategy).order_by(desc(TradeRecommendation.trading_date), desc(TradeRecommendation.generated_at), desc(TradeRecommendation.id))).scalars().all()
        paper = _latest([row for row in recs if row.method == "PAPER_TRADE" and row.action == "BUY"])
        agents = _latest([row for row in recs if row.method == "TRADING_AGENTS" and row.action == "BUY"])
        watch = db.execute(select(AIWatchlist).order_by(desc(AIWatchlist.trading_date), desc(AIWatchlist.score)).limit(20)).scalars().all()
    latest_date = max([row.trading_date for row in paper + agents], default=now.date())
    paper = [row for row in paper if row.trading_date == latest_date]
    agents = [row for row in agents if row.trading_date == latest_date]
    timestamps = [row.data_timestamp for row in paper + agents if row.data_timestamp]
    data_as_of = max(timestamps).astimezone(TZ) if timestamps else now
    market = get_market_status(now)
    paper_symbols = {row.symbol for row in paper}
    agent_symbols = {row.symbol for row in agents}
    overlap = sorted(paper_symbols & agent_symbols)
    watch_latest = _latest(watch)
    divider = "━━━━━━━━━━━━━━━━━━"
    lines = [
        "📈 NEXT TRADING DAY",
        target.strftime("%d %b %Y"),
        "",
        f"Market Context: {market['status']}",
        f"Data as of: {data_as_of.strftime('%d %b %Y %H:%M WIB')}",
        "",
        divider,
        "🤖 TRADINGAGENTS PICKS",
        divider,
        *_pick_lines(agents, ai=True),
        divider,
        "📊 PAPER TRADE PICKS",
        divider,
        *_pick_lines(paper, ai=False),
        divider,
        "🔥 DUAL SIGNAL",
        divider,
        *([f"{symbol} — Consensus: STRONG" for symbol in overlap] or ["NO CONSENSUS"]),
        "",
        divider,
        "👀 AI WATCHLIST",
        divider,
        *([f"{row.symbol} — {row.status}" for row in watch_latest[:5]] or ["NO WATCHLIST CANDIDATES"]),
        "",
        divider,
        "⚡ BSJP / BPJS",
        divider,
        *([f"{row.symbol} — {strategy} / {row.method}" for row in agents[:5]] or [f"{strategy} — NO TRADINGAGENTS PICK"]),
        "",
        "Research / paper trading only. No guaranteed profit; no brokerage order.",
    ]
    return "\n".join(lines)


def send_report(strategy):
    message = build_report(strategy)
    return subprocess.run(["/home/mqdd/.local/bin/hermes", "send", "--to", "telegram", message], check=False, timeout=45).returncode
