import os
from datetime import datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from . import analytics
from .db import SessionLocal
from .market_calendar import TZ, get_market_status, get_trading_sessions, next_trading_day
from .models import Company, DailyPrice, IntradayPrice, PaperTrade
from .recommendation_model import TradeRecommendation
from .ai_trading_model import AITradingAnalysis

MIN_RR=float(os.environ.get("RECOMMENDATION_MIN_RR","1.5"))
SHORTLIST=int(os.environ.get("DAILY_SHORTLIST_SIZE","10"))
TA_MAX=int(os.environ.get("TRADINGAGENTS_MAX_CANDIDATES","5"))
MIN_VALUE=float(os.environ.get("RECOMMENDATION_MIN_AVG_VALUE","1000000000"))
MIN_SAMPLE=int(os.environ.get("MIN_HISTORY_SAMPLE","20"))
BSJP_BEFORE=int(os.environ.get("BSJP_SCAN_MINUTES_BEFORE_CLOSE","45"))
BPJS_AFTER=int(os.environ.get("BPJS_SCAN_MINUTES_AFTER_OPEN","20"))
BPJS_LAST=int(os.environ.get("BPJS_LAST_ENTRY_MINUTES_AFTER_OPEN","120"))

def _data(db, company):
    rows=db.execute(select(DailyPrice).where(DailyPrice.company_id==company.id,DailyPrice.close.is_not(None)).order_by(desc(DailyPrice.date)).limit(252)).scalars().all()[::-1]
    if len(rows)<30:return None
    payload=[{"date":r.date,"open":r.open,"high":r.high,"low":r.low,"close":r.close,"volume":r.volume} for r in rows]
    ind=analytics.technical_indicators(payload) or {}
    intr=db.execute(select(IntradayPrice).where(IntradayPrice.company_id==company.id).order_by(desc(IntradayPrice.timestamp)).limit(1)).scalar_one_or_none()
    now=datetime.now(timezone.utc); live=bool(intr and (now-intr.timestamp).total_seconds()<900)
    price=float(intr.price) if live and intr.price is not None else float(rows[-1].close)
    ts=intr.timestamp if live else datetime.combine(rows[-1].date,datetime.min.time(),tzinfo=timezone.utc)
    avg_value=sum(float(r.close or 0)*float(r.volume or 0) for r in rows[-20:])/20
    avg_vol=sum(float(r.volume or 0) for r in rows[-20:])/20
    rel_vol=float(rows[-1].volume or 0)/avg_vol if avg_vol else 0
    resistance=max(float(r.high or r.close) for r in rows[-20:])
    support=min(float(r.low or r.close) for r in rows[-20:])
    return rows,ind,price,ts,live,avg_value,rel_vol,resistance,support

def _setup(price,atr,resistance,support):
    if not atr or atr<=0:return None
    stop=max(support,price-1.5*atr)
    if stop>=price:stop=price-atr
    risk=price-stop
    tp1=resistance if resistance>price and (resistance-price)/risk>=MIN_RR else price+MIN_RR*risk
    tp2=max(tp1,price+2*risk)
    rr=(tp1-price)/risk if risk else 0
    if rr<MIN_RR:return None
    return {"entry":price,"low":max(stop,price-.25*atr),"high":price+.25*atr,"stop":stop,"tp1":tp1,"tp2":tp2,"rr":rr}

def _valid_until(strategy, now):
    if strategy == "BSJP":
        next_day = next_trading_day(now.date())
        sessions = get_trading_sessions(next_day)
        opening = next((item for item in sessions if item.name == "SESSION_1"), sessions[0])
        return datetime.combine(next_day, opening.start, tzinfo=TZ) + timedelta(hours=2)
    if strategy == "BPJS":
        sessions = get_trading_sessions(now.date())
        if not sessions:
            next_day = next_trading_day(now.date())
            next_sessions = get_trading_sessions(next_day)
            opening = next((item for item in next_sessions if item.name == "SESSION_1"), next_sessions[0])
            return datetime.combine(next_day, opening.start, tzinfo=TZ) + timedelta(hours=2)
        closing = next((item for item in reversed(sessions) if item.name == "SESSION_2"), sessions[-1])
        return datetime.combine(now.date(), closing.end, tzinfo=TZ)
    return now + timedelta(days=1)

def _score(ind,avg_value,rel_vol,price,resistance,strategy):
    trend=(25 if ind.get("sma20") and price>ind["sma20"] else 0)+(15 if ind.get("sma50") and price>ind["sma50"] else 0)
    momentum=(15 if ind.get("rsi14") is not None and 50<=ind["rsi14"]<=68 else 0)+(15 if ind.get("macd") and ind["macd"].get("histogram",0)>0 else 0)
    volume=min(15,max(0,rel_vol*7.5)); liquidity=15 if avg_value>=MIN_VALUE else max(0,15*avg_value/MIN_VALUE)
    score=trend+momentum+volume+liquidity
    if strategy=="BSJP":score+=10 if price>=resistance*.98 else 0
    return min(100,round(score,1)),{"trend":trend,"momentum":momentum,"relative_volume":round(rel_vol,2),"liquidity_value":round(avg_value),"near_resistance":price>=resistance*.98}

def _valid_strategy(strategy,now):
    status=get_market_status(now)
    if not status["is_trading_day"]:return False,"NON_TRADING_DAY",status
    sessions=get_trading_sessions(now.date()); regular=[x for x in sessions if x.name in ("SESSION_1","SESSION_2")]
    if not regular:return False,"NO_SESSION",status
    open_dt=datetime.combine(now.date(),regular[0].start,tzinfo=TZ); close_dt=datetime.combine(now.date(),regular[-1].end,tzinfo=TZ)
    if strategy=="BSJP":
        ok=close_dt-timedelta(minutes=BSJP_BEFORE)<=now<close_dt
        nxt=next_trading_day(now.date()); gap=(nxt-now.date()).days
        if gap>1 and os.environ.get("BSJP_ALLOW_LONG_OVERNIGHT","true").lower() not in ("1","true","yes"):return False,"LONG_OVERNIGHT_EXCLUDED",status
        return ok,"OUTSIDE_BSJP_WINDOW" if not ok else "OK",status
    if strategy=="BPJS":
        ok=open_dt+timedelta(minutes=BPJS_AFTER)<=now<=open_dt+timedelta(minutes=BPJS_LAST)
        return ok,"OUTSIDE_BPJS_WINDOW" if not ok else "OK",status
    return True,"OK",status

def generate_quant(strategy="GENERAL",cycle="daily",now=None,preview=False):
    now=(now or datetime.now(TZ)).astimezone(TZ); allowed,reason,market=_valid_strategy(strategy,now)
    if preview and strategy == "BPJS" and not allowed:
        allowed, reason = True, "STALE_PRICE_PREVIEW"
        market = dict(market); market["status"] = "PREVIEW_CLOSED"
    if not allowed:return {"generated":0,"status":"NO_TRADE","reason":reason,"market":market}
    generated=0
    with SessionLocal() as db:
        companies=db.execute(select(Company).where(Company.symbol!="IHSG")).scalars().all(); candidates=[]
        for c in companies:
            data=_data(db,c)
            if not data:continue
            rows,ind,price,ts,live,avg_value,rel_vol,resistance,support=data
            if strategy in ("BSJP", "BPJS") and not live and not (preview and strategy == "BPJS"): continue
            if avg_value<MIN_VALUE or price<=0:continue
            setup=_setup(price,ind.get("atr14"),resistance,support)
            if not setup:continue
            score,signals=_score(ind,avg_value,rel_vol,price,resistance,strategy)
            threshold=70 if strategy=="GENERAL" else 75
            if score<threshold:continue
            risks=[]
            atr_pct=(ind.get("atr14") or 0)/price*100
            if atr_pct>6:risks.append("ATR tinggi")
            if ind.get("rsi14") and ind["rsi14"]>65:risks.append("Momentum mendekati overbought")
            candidates.append((score,c,setup,signals,risks,ts,live,ind))
        candidates.sort(key=lambda x:x[0],reverse=True)
        for score,c,setup,signals,risks,ts,live,ind in candidates[:SHORTLIST]:
            rec=TradeRecommendation(trading_date=now.date(),symbol=c.symbol,method="PAPER_TRADE",strategy=strategy,cycle=cycle,generated_at=now.astimezone(timezone.utc),data_timestamp=ts,market_status=market["status"],action="BUY",status="PREVIEW" if preview else "ACTIVE",current_price=setup["entry"],entry_price=setup["entry"],entry_low=setup["low"],entry_high=setup["high"],tp1=setup["tp1"],tp2=setup["tp2"],stop_loss=setup["stop"],risk_reward=setup["rr"],score=score,confidence_label="HIGH" if score>=85 else "MEDIUM",valid_until=_valid_until(strategy, now).astimezone(timezone.utc),reasons={"positive":[x for x in ["Harga di atas SMA20" if ind.get("sma20") and setup["entry"]>ind["sma20"] else None,"Harga di atas SMA50" if ind.get("sma50") and setup["entry"]>ind["sma50"] else None,f"Relative volume {signals['relative_volume']}x",f"R/R {setup['rr']:.2f}"] if x],"negative":risks},signals=signals,risks={"items":risks+["Harga terakhir bukan harga live; tunggu market buka" ] if preview else risks,"price_live":live,"stale_preview":preview},outcome={})
            db.add(rec)
            try:db.commit();generated+=1
            except IntegrityError:db.rollback()
    return {"generated":generated,"status":"OK" if generated else "NO_TRADE","reason":None if generated else "NO_QUALIFIED_SETUP","market":market}

def import_tradingagents(strategy="GENERAL", cycle="daily",now=None):
    now=(now or datetime.now(TZ)).astimezone(TZ); market=get_market_status(now); generated=0
    with SessionLocal() as db:
        rows=db.execute(select(AITradingAnalysis).where(AITradingAnalysis.analysis_date==now.date(),AITradingAnalysis.status=="COMPLETED").order_by(desc(AITradingAnalysis.id)).limit(TA_MAX)).scalars().all()
        seen=set()
        for a in rows:
            if a.symbol in seen:continue
            seen.add(a.symbol); result=a.result or {}; setup=(result.get("setup") or {})
            data=db.execute(select(Company).where(Company.symbol==a.symbol)).scalar_one_or_none()
            if not data:continue
            market_data=_data(db,data)
            if not market_data:continue
            _,ind,price,ts,live,_,_,resistance,support=market_data
            deterministic=_setup(price,ind.get("atr14"),resistance,support)
            action="BUY" if a.action=="BUY" and deterministic else "NO_TRADE"
            score={"BUY":80,"HOLD":55,"SELL":25,"NO_TRADE":40}.get(a.action,40)
            reports=(result.get("reports") or {})
            reasons=[reports.get("market_report_id") or reports.get("market_report"),reports.get("fundamentals_report_id") or reports.get("fundamentals_report"),reports.get("news_report_id") or reports.get("news_report")]
            rec=TradeRecommendation(trading_date=now.date(),symbol=a.symbol,method="TRADING_AGENTS",strategy=strategy,cycle=cycle,generated_at=now.astimezone(timezone.utc),data_timestamp=ts,market_status=market["status"],action=action,status="ACTIVE" if action=="BUY" else "NO_TRADE",current_price=price,entry_price=deterministic["entry"] if deterministic else None,entry_low=deterministic["low"] if deterministic else None,entry_high=deterministic["high"] if deterministic else None,tp1=deterministic["tp1"] if deterministic else None,tp2=deterministic["tp2"] if deterministic else None,stop_loss=deterministic["stop"] if deterministic else None,risk_reward=deterministic["rr"] if deterministic else None,score=score,confidence_label="HIGH" if score>=80 else "MEDIUM" if score>=50 else "LOW",valid_until=now.astimezone(timezone.utc)+timedelta(days=1),reasons={"analysis_id":a.id,"sections":[r for r in reasons if r],"decision":a.decision},signals={"source":"TradingAgents structured reports"},risks={"price_live":live},outcome={})
            db.add(rec)
            try:db.commit();generated+=1
            except IntegrityError:db.rollback()
    return {"generated":generated,"status":"OK" if generated else "NO_TRADE","reason":None if generated else "NO_COMPLETED_ANALYSIS","market":market}

def historical_stats(db,strategy):
    trades=db.execute(select(PaperTrade).where(PaperTrade.status=="closed")).scalars().all(); n=len(trades)
    if n<MIN_SAMPLE:return {"status":"INSUFFICIENT_SAMPLE","sample_size":n,"minimum":MIN_SAMPLE}
    pnls=[float(t.pnl or 0) for t in trades]; wins=[x for x in pnls if x>0]; losses=[-x for x in pnls if x<0]
    return {"status":"VALID","sample_size":n,"win_rate":len(wins)/n,"average_win":sum(wins)/len(wins) if wins else 0,"average_loss":sum(losses)/len(losses) if losses else 0,"profit_factor":sum(wins)/sum(losses) if losses else None}


def generate_tradingagents_shortlist(strategy="GENERAL", cycle="daily", now=None):
    """Run TradingAgents only for top persisted quant candidates."""
    from .ai_trading import analyze
    now = (now or datetime.now(TZ)).astimezone(TZ)
    with SessionLocal() as db:
        rows = db.execute(select(TradeRecommendation).where(TradeRecommendation.trading_date == now.date(), TradeRecommendation.method == "PAPER_TRADE", TradeRecommendation.strategy == strategy, TradeRecommendation.action == "BUY").order_by(desc(TradeRecommendation.score)).limit(TA_MAX)).scalars().all()
    completed = 0
    for row in rows:
        try:
            analyze(row.symbol)
            completed += 1
        except Exception:
            continue
    return import_tradingagents(strategy=strategy, cycle=cycle, now=now) if completed else {"generated": 0, "status": "NO_TRADE", "reason": "NO_COMPLETED_TRADINGAGENTS_ANALYSIS"}


def update_outcomes(now=None):
    now=(now or datetime.now(TZ)).astimezone(TZ); updated=0
    with SessionLocal() as db:
        rows=db.execute(select(TradeRecommendation).where(TradeRecommendation.status.in_(["ACTIVE","TP1_HIT"]))).scalars().all()
        for rec in rows:
            company=db.execute(select(Company).where(Company.symbol==rec.symbol)).scalar_one_or_none()
            if not company: continue
            data=_data(db,company)
            if not data: continue
            _,_,price,ts,live,*_=data
            outcome=dict(rec.outcome or {}); entry=float(rec.entry_price or price)
            intraday=db.execute(select(IntradayPrice).where(IntradayPrice.company_id==company.id, IntradayPrice.timestamp>=rec.generated_at).order_by(IntradayPrice.timestamp)).scalars().all()
            highs=[float(item.high) for item in intraday if item.high is not None] or [price]
            lows=[float(item.low) for item in intraday if item.low is not None] or [price]
            move=price-entry; favorable=max(highs)-entry; adverse=min(lows)-entry
            entered=outcome.get("entry_triggered", False) or (rec.entry_low is not None and rec.entry_high is not None and rec.entry_low<=price<=rec.entry_high)
            outcome.update({"last_price":price,"last_data_timestamp":ts.isoformat(),"last_update":now.isoformat(),"entry_triggered":entered,"return_pct":round(move/entry*100,3) if entry else 0,"mfe":max(float(outcome.get("mfe",0)),round(favorable,4)),"mae":min(float(outcome.get("mae",0)),round(adverse,4))})
            if rec.action=="BUY":
                if rec.stop_loss and price<=rec.stop_loss: rec.status="SL_HIT"; outcome["exit_reason"]="SL_HIT"
                elif rec.tp2 and price>=rec.tp2: rec.status="TP2_HIT"; outcome["exit_reason"]="TP2_HIT"
                elif rec.tp1 and price>=rec.tp1: rec.status="TP1_HIT"; outcome["tp1_hit"]=True
            if rec.valid_until and now.astimezone(timezone.utc)>rec.valid_until and rec.status not in ("SL_HIT","TP2_HIT"):
                rec.status="EXPIRED"; outcome["exit_reason"]="EXPIRED"
            rec.outcome=outcome; updated+=1
        db.commit()
    return {"updated":updated,"timestamp":now.isoformat()}
