import asyncio, json, os, re, time
from datetime import date
from threading import Lock
import httpx
from sqlalchemy import select
from .config import get_settings
from .db import SessionLocal
from .ai_trading_model import AITradingAnalysis

_lock=Lock()
def normalize_symbol(value):
    symbol=value.upper().strip().removesuffix('.JK')
    if not re.fullmatch(r'[A-Z0-9]{1,8}',symbol): raise ValueError('Invalid IDX symbol')
    return symbol

def _models():
    s=get_settings(); headers={'Authorization':f'Bearer {s.nine_router_api_key}'} if s.nine_router_api_key else {}
    r=httpx.get(f'{s.nine_router_url}/models',headers=headers,timeout=10); r.raise_for_status(); return {x['id'] for x in r.json().get('data',[])}

def _fetch_local_news(symbol: str) -> str:
    """Fetch recent news from the app's own news table (Google News RSS)."""
    from sqlalchemy import select, desc
    from .models import Company, News
    try:
        with SessionLocal() as db:
            company = db.execute(select(Company).where(Company.symbol == symbol)).scalar_one_or_none()
            if not company: return ""
            rows = db.execute(select(News).where(News.company_id == company.id).order_by(desc(News.published_at)).limit(15)).scalars().all()
            if not rows: return ""
            lines = []
            for n in rows:
                src = n.source or "unknown"
                dt = str(n.published_at.date()) if n.published_at else "?"
                title = (n.title or "").strip()[:200]
                summary = (n.summary or "").strip()[:300]
                lines.append(f"[{dt}] {title} ({src})\n  {summary}")
            return "\n".join(lines)
    except Exception:
        return ""

def _translate_to_indonesian(texts: list[str]) -> list[str]:
    """Batch-translate reasoning sections to Indonesian via 9Router. Returns translated list."""
    if not texts or not any(texts):
        return texts
    s=get_settings(); headers={'Authorization':f'Bearer {s.nine_router_api_key}'} if s.nine_router_api_key else {}
    numbered=[f"[{i}]{t}" for i,t in enumerate(texts) if t]
    prompt="Terjemahkan SELURUH teks analisis berikut ke Bahasa Indonesia, termasuk judul, label, rekomendasi, tindakan, alasan, ringkasan, dan isi tabel. Pertahankan format Markdown, bullet, angka, ticker, level harga, serta marker [N]. Jangan sisakan kalimat atau heading bahasa Inggris. Kembalikan satu blok terjemahan untuk setiap marker [N].\n\n" + "\n\n".join(numbered)
    try:
        r=httpx.post(f"{s.nine_router_url}/chat/completions",headers={**headers,"Content-Type":"application/json"},json={"model":"cx/gpt-5.5","messages":[{"role":"user","content":prompt}],"temperature":0.0},timeout=180)
        r.raise_for_status(); out=r.json()["choices"][0]["message"]["content"]
        parts={}; current=None; buf=[]
        for line in out.splitlines():
            m=re.match(r"^\[(\d+)\]",line)
            if m:
                if current is not None: parts[current]="\n".join(buf)
                current=int(m.group(1)); buf=[line]
            elif current is not None: buf.append(line)
        if current is not None: parts[current]="\n".join(buf)
        result=[]
        for i,t in enumerate(texts):
            tr=parts.get(i)
            result.append(tr if tr and len(tr)>20 else t)
        return result
    except Exception: return texts

def _normalize(decision):
    d=str(decision).strip(); low=d.lower()
    if 'strong overweight' in low or 'overweight' in low: return 'BUY'
    if 'strong underweight' in low or 'underweight' in low: return 'SELL'
    return 'HOLD' if 'market weight' in low or 'hold' in low else 'NO_TRADE'

def analyze(symbol, quick_model=None, deep_model=None):
    s=get_settings(); symbol=normalize_symbol(symbol)
    if not s.ai_trading_enabled: raise RuntimeError('AI trading disabled')
    with _lock:
        models=_models(); quick=quick_model or 'cx/gpt-5.4-mini'; deep=deep_model or 'cx/gpt-5.5'
        if quick not in models or deep not in models: raise RuntimeError('Configured TradingAgents model unavailable')
        os.environ.pop('OPENAI_API_KEY',None); os.environ['OPENAI_COMPATIBLE_API_KEY']=s.nine_router_api_key; os.environ['TRADINGAGENTS_LLM_PROVIDER']='openai_compatible'; os.environ['TRADINGAGENTS_LLM_BACKEND_URL']='http://127.0.0.1:20128/v1'; os.environ['TRADINGAGENTS_OUTPUT_LANGUAGE']='Bahasa Indonesia'
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        c=DEFAULT_CONFIG.copy(); c.update(llm_provider='openai_compatible',backend_url='http://127.0.0.1:20128/v1',quick_think_llm=quick,deep_think_llm=deep,max_debate_rounds=1,max_risk_discuss_rounds=1,llm_max_retries=0,request_timeout=60,max_recur_limit=40,output_language='Bahasa Indonesia')
        import tradingagents.dataflows.interface as _iface

        _orig_news = _iface.get_news_yfinance

        def _hybrid_news_getter(ticker, start_date, end_date):
            news = _fetch_local_news(normalize_symbol(ticker))
            if news:
                return f"# News for {ticker} from local Google News RSS sources\n{news}"
            return _orig_news(ticker, start_date, end_date)

        _iface.get_news_yfinance = _hybrid_news_getter
        started=time.monotonic(); state,decision=TradingAgentsGraph(selected_analysts=('market','news','fundamentals'),config=c).propagate(f'{symbol}.JK',date.today()); runtime=time.monotonic()-started
        action=_normalize(decision); reports={k:state.get(k,'') for k in ('market_report','news_report','fundamentals_report','investment_plan','trader_investment_plan','final_trade_decision','risk_debate_state','invest_debate_state')}; _keys=[k for k in ('market_report','news_report','fundamentals_report','investment_plan','trader_investment_plan','final_trade_decision') if reports.get(k)]; _orig=[reports[k] for k in _keys]; _trans=_translate_to_indonesian(_orig); reports.update({k+'_id':t for k,t in zip(_keys,_trans)}); result={'ticker':symbol,'analysis_date':str(date.today()),'decision':str(decision),'action':action,'confidence':0,'runtime_seconds':runtime,'reports':reports,'final_reason':str(decision)}
        with SessionLocal() as db:
            row=AITradingAnalysis(symbol=symbol,analysis_date=date.today(),decision=str(decision),action=action,confidence=0,runtime_seconds=runtime,result=result,raw_result=json.loads(json.dumps({'decision':decision,'state':state},default=str))); db.add(row); db.commit(); db.refresh(row); result['id']=row.id
        return result

def queue_analysis(symbol): return asyncio.to_thread(analyze,symbol)
