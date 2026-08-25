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
        os.environ.pop('OPENAI_API_KEY',None); os.environ['OPENAI_COMPATIBLE_API_KEY']=s.nine_router_api_key; os.environ['TRADINGAGENTS_LLM_PROVIDER']='openai_compatible'; os.environ['TRADINGAGENTS_LLM_BACKEND_URL']='http://127.0.0.1:20128/v1'
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        c=DEFAULT_CONFIG.copy(); c.update(llm_provider='openai_compatible',backend_url='http://127.0.0.1:20128/v1',quick_think_llm=quick,deep_think_llm=deep,max_debate_rounds=1,max_risk_discuss_rounds=1,llm_max_retries=0,request_timeout=60,max_recur_limit=40)
        started=time.monotonic(); state,decision=TradingAgentsGraph(selected_analysts=('market','news','fundamentals'),config=c).propagate(f'{symbol}.JK',date.today()); runtime=time.monotonic()-started
        action=_normalize(decision); reports={k:state.get(k,'') for k in ('market_report','news_report','fundamentals_report','investment_plan','trader_investment_plan','final_trade_decision','risk_debate_state','invest_debate_state')}; result={'ticker':symbol,'analysis_date':str(date.today()),'decision':str(decision),'action':action,'confidence':0,'runtime_seconds':runtime,'reports':reports,'final_reason':str(decision)}
        with SessionLocal() as db:
            row=AITradingAnalysis(symbol=symbol,analysis_date=date.today(),decision=str(decision),action=action,confidence=0,runtime_seconds=runtime,result=result,raw_result=json.loads(json.dumps({'decision':decision,'state':state},default=str))); db.add(row); db.commit(); db.refresh(row); result['id']=row.id
        return result

def queue_analysis(symbol): return asyncio.to_thread(analyze,symbol)
