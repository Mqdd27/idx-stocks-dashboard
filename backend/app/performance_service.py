from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .recommendation_model import TradeRecommendation
TZ = ZoneInfo("Asia/Jakarta")
METHODS = {"TRADING_AGENTS", "PAPER_TRADE"}
PERIODS = {"daily", "weekly", "monthly", "yearly"}
def period_bounds(period, day):
    if period == "daily": return day, day
    if period == "weekly":
        start = day - timedelta(days=day.weekday()); return start, start + timedelta(days=6)
    if period == "monthly":
        start = day.replace(day=1); end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1); return start, end
    if period == "yearly": return day.replace(month=1, day=1), day.replace(month=12, day=31)
    raise ValueError("Invalid period")
def _metrics(rows, strategy, method, period, start, end):
    returns=[]; signals=triggered=not_triggered=open_positions=anomalies=0
    for row in rows:
        if row.strategy != strategy or (method and row.method != method) or not start <= row.trading_date <= end: continue
        signals += 1; outcome=row.outcome or {}; entered=bool(outcome.get("entry_triggered")); triggered += int(entered)
        status=(row.status or "").upper(); value=outcome.get("return_pct")
        exit_date=outcome.get("exit_date") or outcome.get("exit_trading_date")
        if strategy == "BPJS" and entered and exit_date and str(exit_date) != str(row.trading_date):
            anomalies += 1; continue
        if not entered: not_triggered += int(status == "EXPIRED"); continue
        if status in {"ACTIVE", "TP1_HIT", "PREVIEW"}: open_positions += 1; continue
        if value is not None: returns.append(float(value))
    wins=[x for x in returns if x > 0]; losses=[x for x in returns if x < 0]; factor=sum(wins)/abs(sum(losses)) if losses else ("INF" if wins else None); compounded=1
    for value in returns: compounded *= 1 + value / 100
    return {"strategy":strategy,"method":method or "COMBINED","period":period,"period_start":str(start),"period_end":str(end),"signals":signals,"triggered":triggered,"not_triggered":not_triggered,"trades":len(returns),"winning_trades":len(wins),"losing_trades":len(losses),"breakeven_trades":len(returns)-len(wins)-len(losses),"win_rate":round(len(wins)/len(returns)*100,3) if returns else None,"loss_rate":round(len(losses)/len(returns)*100,3) if returns else None,"gross_return_pct":round(sum(wins),3),"net_return_pct":round((compounded-1)*100,3) if returns else 0,"average_return_pct":round(sum(returns)/len(returns),3) if returns else 0,"average_win_pct":round(sum(wins)/len(wins),3) if wins else None,"average_loss_pct":round(sum(losses)/len(losses),3) if losses else None,"best_trade_pct":round(max(returns),3) if returns else None,"worst_trade_pct":round(min(returns),3) if returns else None,"profit_factor":round(factor,3) if isinstance(factor,float) else factor,"open_positions":open_positions,"anomalies":anomalies,"status":"NO_TRADES" if not returns else "INSUFFICIENT_SAMPLE" if len(returns)<20 else "FINAL","sample_quality":"LOW SAMPLE" if len(returns)<20 else "SUFFICIENT"}
def get_performance(db, strategy, period="daily", as_of=None, method=None):
    if strategy not in {"BSJP", "BPJS"} or period not in PERIODS or method not in (None, *METHODS): raise ValueError("Invalid performance request")
    day=as_of or datetime.now(TZ).date(); start,end=period_bounds(period,day); rows=db.execute(select(TradeRecommendation).where(TradeRecommendation.strategy==strategy)).scalars().all(); methods=[method] if method else list(METHODS)
    return {"strategy":strategy,"period":period,"period_start":str(start),"period_end":str(end),"data":[_metrics(rows,strategy,m,period,start,end) for m in methods],"combined":_metrics(rows,strategy,None,period,start,end),"generated_at":datetime.now(TZ).isoformat(),"attribution":"strategy_date=entry trading date"}
