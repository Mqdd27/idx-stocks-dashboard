import asyncio
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select
from .ai_trading import analyze, normalize_symbol
from .ai_trading_model import AITradingAnalysis, AITradingJob
from .config import get_settings
from .db import SessionLocal

router = APIRouter(prefix='/api/ai-trading', tags=['ai-trading'])



def _atr_setup(db, symbol: str, action: str):
    """Deterministic entry/TP/SL/RR from daily prices (ATR-based). LLM prices are ignored."""
    from .main import analytics
    from .models import Company, DailyPrice
    company = db.execute(select(Company).where(Company.symbol == symbol)).scalar_one_or_none()
    if not company:
        return None
    rows = db.execute(select(DailyPrice).where(DailyPrice.company_id == company.id, DailyPrice.close.is_not(None)).order_by(desc(DailyPrice.date)).limit(30)).scalars().all()[::-1]
    if len(rows) < 5:
        return None
    trs = []
    for prev, cur in zip(rows, rows[1:]):
        hi, lo = float(cur.high or cur.close), float(cur.low or cur.close)
        cp = float(prev.close)
        trs.append(max(hi - lo, abs(hi - cp), abs(lo - cp)))
    atr = sum(trs) / len(trs) if trs else float(rows[-1].close) * 0.02
    entry = float(rows[-1].close)
    if action != 'BUY':
        return {'action': action, 'note': 'Setup beli tidak dibuat untuk sinyal selain BUY.', 'entry': entry}
    stop = entry - 1.5 * atr
    target = entry + 3.0 * atr
    return {
        'action': action,
        'entry': round(entry, 2),
        'stop_loss': round(stop, 2),
        'take_profit': round(target, 2),
        'risk_reward': 2.0,
        'atr': round(atr, 2),
        'basis': 'entry=harga penutupan terakhir, SL=entry-1,5xATR(30h), TP=entry+3,0xATR (deterministik)',
    }


def _clean_report(text):
    """Strip [N] translation markers and redundant FINAL TRANSACTION PROPOSAL prefix."""
    import re
    if not text:
        return None
    cleaned = str(text).strip()
    cleaned = re.sub(r'^\[\d+\]\s*', '', cleaned)
    cleaned = re.sub(
        r'^(?:FINAL TRANSACTION PROPOSAL|PROPOSAL TRANSAKSI AKHIR):\s*\*\*[^*]+\*\*\s*',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )
    replacements = (
        ('Strong Overweight', 'Sangat Di Atas Bobot Acuan'),
        ('Strong Underweight', 'Sangat Di Bawah Bobot Acuan'),
        ('Market Weight', 'Sesuai Bobot Pasar'),
        ('Overweight', 'Di Atas Bobot Acuan'),
        ('Underweight', 'Di Bawah Bobot Acuan'),
        ('Executive Summary', 'Ringkasan Eksekutif'),
        ('Investment Thesis', 'Tesis Investasi'),
        ('Strategic Actions', 'Tindakan Strategis'),
        ('Recommendation', 'Rekomendasi'),
        ('Reasoning', 'Penalaran'),
        ('Rationale', 'Alasan'),
        ('Position Sizing', 'Ukuran Posisi'),
        ('Stop Loss', 'Batas Rugi'),
        ('Action', 'Tindakan'),
    )
    for english, indonesian in replacements:
        cleaned = re.sub(re.escape(english), indonesian, cleaned, flags=re.IGNORECASE)
    return cleaned or None

def _reasoning(result: dict | None):
    reports = (result or {}).get('reports') or {}
    raw_state = (result or {}).get('_state') or {}
    invest = raw_state.get('investment_debate_state') or {}
    risk = raw_state.get('risk_debate_state') or {}

    bull_text = None
    bear_text = None
    judge_text = None
    if isinstance(invest, dict):
        bh = invest.get('bull_history')
        eh = invest.get('bear_history')
        if isinstance(bh, list) and bh:
            bull_text = str(bh[-1]) if len(bh) > 0 else None
        elif isinstance(bh, str) and bh:
            bull_text = bh
        if isinstance(eh, list) and eh:
            bear_text = str(eh[-1]) if len(eh) > 0 else None
        elif isinstance(eh, str) and eh:
            bear_text = eh
    if isinstance(risk, dict):
        jd = risk.get('judge_decision')
        if isinstance(jd, str) and jd.strip():
            judge_text = jd

    return [
        {'agent': 'Analis Pasar / Teknikal', 'content': _clean_report(reports.get('market_report_id') or reports.get('market_report'))},
        {'agent': 'Analis Berita', 'content': _clean_report(reports.get('news_report_id') or reports.get('news_report'))},
        {'agent': 'Analis Fundamental', 'content': _clean_report(reports.get('fundamentals_report_id') or reports.get('fundamentals_report'))},
        {'agent': 'Peneliti Bullish', 'content': _clean_report(bull_text)},
        {'agent': 'Peneliti Bearish', 'content': _clean_report(bear_text)},
        {'agent': 'Manajer Riset', 'content': _clean_report(reports.get('investment_plan_id') or reports.get('investment_plan'))},
        {'agent': 'Rekomendasi Trader & Setup', 'content': _clean_report(reports.get('trader_investment_plan_id') or reports.get('trader_investment_plan'))},
        {'agent': 'Analisis Risiko', 'content': _clean_report(judge_text)},
        {'agent': 'Keputusan Akhir Portofolio', 'content': _clean_report(reports.get('final_trade_decision_id') or reports.get('final_trade_decision'))},
    ]

@router.get('/status')
def status():
    settings = get_settings()
    try:
        import httpx
        headers = {'Authorization': f'Bearer {settings.nine_router_api_key}'} if settings.nine_router_api_key else {}
        response = httpx.get(f'{settings.nine_router_url}/models', headers=headers, timeout=5)
        reachable = response.is_success
        models = [item['id'] for item in response.json().get('data', [])] if reachable else []
    except Exception:
        reachable, models = False, []
    with SessionLocal() as db:
        last = db.execute(select(AITradingAnalysis).order_by(desc(AITradingAnalysis.created_at)).limit(1)).scalar_one_or_none()
    return {'enabled': settings.ai_trading_enabled, 'tradingagents_installed': True, 'nine_router_reachable': reachable, 'quick_model': settings.ai_trading_quick_model, 'deep_model': settings.ai_trading_deep_model, 'available_models': models, 'last_analysis': last.created_at if last else None}

@router.get('/jobs')
def jobs():
    with SessionLocal() as db:
        rows = db.execute(select(AITradingJob).order_by(desc(AITradingJob.created_at)).limit(50)).scalars().all()
    return [{'id': r.id, 'symbol': r.symbol, 'status': r.status, 'analysis_id': r.analysis_id, 'error': r.error_message, 'created_at': r.created_at, 'updated_at': r.updated_at} for r in rows]

@router.get('/positions')
def positions():
    from .main import paper_positions
    return paper_positions()

@router.get('/performance')
def performance():
    from .main import paper_summary
    return paper_summary()

@router.get('/history')
def history(limit: int = 50):
    with SessionLocal() as db:
        rows = db.execute(select(AITradingAnalysis).order_by(desc(AITradingAnalysis.created_at)).limit(min(limit, 200))).scalars().all()
    return [{'id': row.id, 'symbol': row.symbol, 'date': row.analysis_date, 'decision': row.decision, 'action': row.action, 'confidence': row.confidence, 'runtime_seconds': row.runtime_seconds, 'status': row.status, 'result': row.result} for row in rows]

@router.get('/analysis/{ticker}')
def latest(ticker: str):
    try:
        symbol = normalize_symbol(ticker)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with SessionLocal() as db:
        row = db.execute(select(AITradingAnalysis).where(AITradingAnalysis.symbol == symbol).order_by(desc(AITradingAnalysis.created_at)).limit(1)).scalar_one_or_none()
    if not row:
        raise HTTPException(404, 'Analysis not found')
    with SessionLocal() as db:
        setup = _atr_setup(db, row.symbol, row.action)
    return {'id': row.id, 'symbol': row.symbol, 'decision': row.decision, 'action': row.action, 'confidence': row.confidence, 'runtime_seconds': row.runtime_seconds, 'status': row.status, 'setup': setup, 'reasoning': [r for r in _reasoning(row.result) if r['content']], 'result': row.result}

@router.post('/analyze/{ticker}', status_code=202)
async def request_analysis(ticker: str, request: Request):
    settings = get_settings()
    if not settings.ai_trading_enabled:
        raise HTTPException(503, 'AI trading disabled')
    try:
        symbol = normalize_symbol(ticker)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    try:
        body = await request.json()
    except Exception:
        body = {}
    quick = body.get('quick_model') or settings.ai_trading_quick_model
    deep = body.get('deep_model') or settings.ai_trading_deep_model
    try:
        import httpx
        headers = {'Authorization': f'Bearer {settings.nine_router_api_key}'} if settings.nine_router_api_key else {}
        response = httpx.get(f'{settings.nine_router_url}/models', headers=headers, timeout=5)
        available = {item['id'] for item in response.json().get('data', [])}
    except Exception:
        raise HTTPException(503, '9Router model list unavailable')
    if quick not in available or deep not in available:
        raise HTTPException(400, 'Selected model is not available in 9Router')
    with SessionLocal() as db:
        active = db.execute(select(AITradingJob).where(AITradingJob.status.in_(['QUEUED', 'RUNNING'])).limit(1)).scalar_one_or_none()
        if active:
            raise HTTPException(409, 'An AI analysis is already queued or running')
        job = AITradingJob(symbol=symbol, status='QUEUED')
        db.add(job); db.commit(); db.refresh(job); job_id = job.id
    async def worker():
        with SessionLocal() as db:
            row = db.get(AITradingJob, job_id); row.status = 'RUNNING'; db.commit()
        try:
            result = await asyncio.to_thread(analyze, symbol, quick, deep)
            with SessionLocal() as db:
                row = db.get(AITradingJob, job_id); row.status = 'COMPLETED'; row.analysis_id = result.get('id'); db.commit()
        except Exception as exc:
            with SessionLocal() as db:
                row = db.get(AITradingJob, job_id); row.status = 'FAILED'; row.error_message = str(exc)[:500]; db.commit()
    asyncio.create_task(worker())
    return {'status': 'QUEUED', 'symbol': symbol, 'job_id': job_id, 'quick_model': quick, 'deep_model': deep}
