import asyncio
import json
import os
import sys
from pathlib import Path
from threading import Lock

import uvicorn

if getattr(sys, "frozen", False):
    sys.path[:0] = [str(Path(sys._MEIPASS) / "backend"), str(Path(sys._MEIPASS))]

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def load_runtime_env() -> None:
    if len(sys.argv) < 2:
        return
    env_path = Path(sys.argv[1])
    try:
        values = json.loads(env_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid desktop environment file: {exc}") from exc
    if not isinstance(values, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in values.items()
    ):
        raise SystemExit("Invalid desktop environment values")
    os.environ.update(values)


def is_loopback(request: Request) -> bool:
    return request.client is not None and request.client.host in {"127.0.0.1", "::1"}

def seed_companies() -> None:
    from sqlalchemy import select

    from app import models as db_models
    from app.db import SessionLocal

    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    companies = json.loads((root / "collector" / "seed_companies.json").read_text())
    db = SessionLocal()
    try:
        for row in companies:
            symbol = row["symbol"].upper()
            if db.execute(select(db_models.Company.id).where(db_models.Company.symbol == symbol)).scalar_one_or_none() is None:
                db.add(db_models.Company(
                    symbol=symbol,
                    company_name=row.get("company_name") or symbol,
                    sector=row.get("sector"),
                    subsector=row.get("subsector"),
                    yahoo_symbol=row.get("yahoo_symbol"),
                ))
        db.commit()
    finally:
        db.close()


BOOTSTRAP_PROGRESS = {"running": False, "completed": 0, "succeeded": 0, "total": 0}
BOOTSTRAP_LOCK = Lock()


def bootstrap_progress() -> dict:
    with BOOTSTRAP_LOCK:
        return BOOTSTRAP_PROGRESS.copy()


def update_bootstrap_progress(**values: int | bool) -> None:
    with BOOTSTRAP_LOCK:
        BOOTSTRAP_PROGRESS.update(values)


CORE_SYMBOLS = (
    "IHSG", "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "ICBP", "INDF",
    "UNTR", "AMRT", "CPIN", "MDKA", "ANTM", "INCO", "ADRO", "PTBA", "ITMG",
    "PGAS", "MEDC", "PGEO", "GOTO", "TPIA", "BRPT", "PANI", "CUAN", "DSSA",
    "KLBF", "SIDO", "MYOR", "UNVR", "HMSP", "EXCL", "ISAT", "MTEL", "TOWR",
    "JSMR", "WIKA", "ADHI", "PTPP", "SMGR", "INTP", "JPFA", "AALI", "LSIP",
    "BBTN", "BRIS", "ARTO", "ESSA", "HEAL", "MIKA",
)


def bootstrap_prices() -> None:
    from sqlalchemy import select

    from app import models as db_models
    from app.db import SessionLocal
    from collector.daily_sync import store_daily_rows
    from collector import yahoo

    db = SessionLocal()
    try:
        rows = db.execute(
            select(db_models.Company.symbol, db_models.Company.yahoo_symbol)
            .where(db_models.Company.symbol.in_(CORE_SYMBOLS))
        ).all()
    finally:
        db.close()

    update_bootstrap_progress(running=True, completed=0, succeeded=0, total=len(rows))

    async def sync() -> None:
        import httpx

        semaphore = asyncio.Semaphore(8)

        async def fetch(symbol: str, yahoo_symbol: str):
            async with semaphore:
                try:
                    async with httpx.AsyncClient(timeout=12) as client:
                        chart = await yahoo.fetch_chart(yahoo_symbol, "1y", "1d", client=client)
                    return symbol, chart
                except Exception:
                    return symbol, None

        charts = await asyncio.gather(*(fetch(symbol, yahoo_symbol) for symbol, yahoo_symbol in rows))
        for symbol, chart in charts:
            succeeded = bootstrap_progress()["succeeded"]
            if chart:
                db = SessionLocal()
                try:
                    company = db.execute(
                        select(db_models.Company).where(db_models.Company.symbol == symbol)
                    ).scalar_one()
                finally:
                    db.close()
                store_daily_rows(company.id, yahoo.chart_to_daily_rows(chart))
                succeeded += 1
            update_bootstrap_progress(completed=bootstrap_progress()["completed"] + 1, succeeded=succeeded)

    try:
        asyncio.run(sync())
    finally:
        update_bootstrap_progress(running=False)


def maybe_bootstrap_prices() -> None:
    from sqlalchemy import select

    from app import models as db_models
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        has_price = db.execute(
            select(db_models.DailyPrice.id).limit(1)
        ).scalar_one_or_none() is not None
    finally:
        db.close()
    if not has_price:
        import threading

        threading.Thread(target=bootstrap_prices, name="desktop-price-bootstrap", daemon=True).start()
    else:
        update_bootstrap_progress(running=False, completed=0, succeeded=0, total=0)


def sync_once() -> dict:
    from collector.daily_sync import all_symbols, load_seed, sync_fundamentals, sync_prices
    from collector.news import sync_news
    from scripts.foreign_flow_ingest import ingest_latest_available
    from scripts.broker_activity_ingest import ingest
    from shared.common import now_wib, upsert_companies

    upsert_companies(load_seed())
    symbols = all_symbols()
    asyncio.run(sync_prices(symbols))
    asyncio.run(sync_fundamentals(symbols))
    names = {symbol: symbol for symbol, _ in symbols}
    asyncio.run(sync_news(symbols, names))
    try:
        flow = ingest_latest_available(now_wib().date())
        ingest(flow["date"])
    except Exception:
        pass
    return {"symbols": len(symbols), "at": now_wib().isoformat()}


def main() -> None:
    load_runtime_env()
    from app.config import get_settings
    from app.db import init_db
    from app.main import app
    from app.security import valid_symbol

    settings = get_settings()
    static_dir = Path(settings.desktop_static_dir)
    init_db()
    seed_companies()
    maybe_bootstrap_prices()
    if os.environ.get("DESKTOP_SYNC_ONLY") == "1":
        print(json.dumps(sync_once()))
        return

    if settings.desktop_local_auth:
        @app.middleware("http")
        async def desktop_local_auth(request: Request, call_next):
            if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/") and not is_loopback(request):
                raise HTTPException(403, "Desktop API only accepts local connections")
            return await call_next(request)

    @app.get("/api/desktop/bootstrap-status", include_in_schema=False)
    def desktop_bootstrap_status():
        return JSONResponse(bootstrap_progress())

    if static_dir.exists():
        @app.get("/stock/{symbol}", include_in_schema=False)
        def desktop_stock_page(symbol: str):
            if not valid_symbol(symbol):
                raise HTTPException(404)
            page = static_dir / "stock" / f"{symbol.upper()}.html"
            if not page.is_file():
                raise HTTPException(404)
            return FileResponse(page)

        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="desktop-static")

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("DESKTOP_PORT", "8200")), log_level="info")


if __name__ == "__main__":
    main()
