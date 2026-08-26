"""TradingAgents reasoning connected to the existing deterministic paper engine."""
from datetime import date, datetime, timezone

from sqlalchemy import desc, select

from . import analytics
from .ai_auto_trade_model import AIAutoTradeConfig, AIAutoTradeRun
from .ai_trading import analyze
from .db import SessionLocal
from .market_calendar import get_market_status
from .models import Company, DailyPrice, PaperAuditEvent, PaperBotConfig, PaperTrade
from .paper_trading import decide, size_position


def get_config(db):
    config = db.execute(select(AIAutoTradeConfig).limit(1)).scalar_one_or_none()
    if not config:
        config = AIAutoTradeConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def select_candidates(db, limit: int) -> list[dict]:
    # Reuse the existing cheap scanner. LLM analysis starts only after ranking.
    from .main import paper_candidates

    rows = paper_candidates(force=True, limit=1000, db=db)["data"]
    eligible = [row for row in rows if row.get("action") == "buy"]
    eligible.sort(key=lambda row: (float(row.get("score") or 0), float(row.get("risk_reward") or 0)), reverse=True)
    return eligible[:limit]


def _open_paper_trade(db, run_id: int, symbol: str, analysis: dict) -> tuple[bool, str]:
    from .main import _execution_snapshot, _paper_config

    paper = _paper_config(db)
    if not paper.enabled:
        return False, "PAPER_BOT_DISABLED"
    if analysis.get("action") != "BUY":
        return False, f"AI_{analysis.get('action', 'NO_TRADE')}"
    if db.execute(select(PaperTrade).where(PaperTrade.symbol == symbol, PaperTrade.status == "open")).scalar_one_or_none():
        return False, "DUPLICATE_OPEN_POSITION"

    if db.execute(select(PaperTrade).where(PaperTrade.symbol == symbol, PaperTrade.entry_date == date.today())).scalar_one_or_none():
        return False, "DUPLICATE_TODAY"

    open_trades = db.execute(select(PaperTrade).where(PaperTrade.status == "open")).scalars().all()
    if len(open_trades) >= int(paper.max_positions):
        return False, "MAX_OPEN_POSITIONS"

    company = db.execute(select(Company).where(Company.symbol == symbol)).scalar_one()
    now = datetime.now(timezone.utc)
    snapshot = _execution_snapshot(db, company.id, now)
    if not snapshot:
        return False, "NO_CURRENT_PRICE"

    rows = db.execute(
        select(DailyPrice)
        .where(DailyPrice.company_id == company.id, DailyPrice.close.is_not(None))
        .order_by(desc(DailyPrice.date)).limit(280)
    ).scalars().all()[::-1]
    indicators = analytics.technical_indicators([
        {"date": row.date, "open": row.open, "high": row.high, "low": row.low, "close": row.close, "volume": row.volume}
        for row in rows
    ]) or {}
    indicators["last_price"] = snapshot["price"]
    setup = decide(indicators, float(paper.min_score), float(paper.min_rr))
    if setup.action != "buy" or setup.stop is None or setup.target is None:
        return False, f"DETERMINISTIC_GATE: {setup.reason}"

    exposure = sum(float(trade.entry_price) * int(trade.quantity) * 100 for trade in open_trades)
    available = max(0.0, float(paper.cash) - exposure)
    quantity = size_position(
        available, snapshot["price"], setup.stop, float(paper.risk_per_trade),
        float(paper.fee_rate), float(paper.slippage_rate), float(paper.max_exposure),
    )
    if quantity <= 0:
        return False, "POSITION_SIZE_ZERO"

    run_key = f"ai-auto-{date.today().isoformat()}-{run_id}"
    fill = snapshot["price"] * (1 + float(paper.slippage_rate))
    trade = PaperTrade(
        symbol=symbol, entry_date=snapshot["date"], entry_timestamp=now,
        entry_price=fill, quantity=quantity, stop_loss=setup.stop,
        take_profit=setup.target, score=setup.score,
        reason=f"TradingAgents={analysis.get('decision')}; {setup.reason}", run_key=run_key,
    )
    db.add(trade)
    db.add(PaperAuditEvent(
        event_type="ai_trade_opened", symbol=symbol,
        payload={"run_id": run_id, "analysis_id": analysis.get("id"), "entry": fill, "stop": setup.stop, "target": setup.target, "rr": setup.risk_reward},
    ))
    db.commit()
    return True, "OPENED"


def execute_run(run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(AIAutoTradeRun, run_id)
        run.status = "RUNNING"
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        try:
            market = get_market_status()
            if not market["is_trading_day"]:
                raise RuntimeError(f"IDX_NON_TRADING_DAY: {market['status']}")
            if not market["is_open"]:
                raise RuntimeError(f"IDX_MARKET_NOT_OPEN: {market['status']}")

            config = get_config(db)
            candidates = select_candidates(db, int(config.max_candidates))
            run.candidates = candidates
            db.commit()

            results = []
            created = 0
            for candidate in candidates:
                symbol = candidate["symbol"]
                try:
                    analysis = analyze(symbol, config.quick_model, config.deep_model)
                    opened, reason = _open_paper_trade(db, run_id, symbol, analysis)
                    created += int(opened)
                    results.append({"symbol": symbol, "analysis_id": analysis.get("id"), "decision": analysis.get("decision"), "action": analysis.get("action"), "trade_opened": opened, "reason": reason})
                except Exception as exc:
                    results.append({"symbol": symbol, "action": "FAILED", "trade_opened": False, "reason": str(exc)[:500]})

            run = db.get(AIAutoTradeRun, run_id)
            run.results = results
            run.trades_created = created
            run.status = "COMPLETED"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            run = db.get(AIAutoTradeRun, run_id)
            run.status = "FAILED"
            run.error_message = str(exc)[:500]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
