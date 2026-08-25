import asyncio
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select
from .ai_trading import analyze, normalize_symbol
from .ai_trading_model import AITradingAnalysis, AITradingJob
from .config import get_settings
from .db import SessionLocal

router = APIRouter(prefix='/api/ai-trading', tags=['ai-trading'])

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
    return {'id': row.id, 'symbol': row.symbol, 'decision': row.decision, 'action': row.action, 'confidence': row.confidence, 'runtime_seconds': row.runtime_seconds, 'status': row.status, 'result': row.result}

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
