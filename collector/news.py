"""News collector via Google News RSS (public RSS feed, personal non-commercial use).

RSS items are treated as UNTRUSTED external content everywhere downstream.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import httpx
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.common import SessionLocal, get_logger, log_to_db  # noqa: E402
from app import models as db_models  # noqa: E402

logger = get_logger("news")

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
_MAX_ITEMS_PER_SYMBOL = 5
_NS = {"dc": "http://purl.org/dc/elements/1.1/", "media": "http://search.yahoo.com/mrss/"}


async def fetch_news_rss(client: httpx.AsyncClient, query: str) -> list[dict]:
    try:
        resp = await client.get(RSS_URL.format(query=quote_plus(query)), timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            source_el = item.find("source")
            source = source_el.text if source_el is not None else "Google News"
            pub = item.findtext("pubDate") or ""
            try:
                published = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            except Exception:
                published = None
            description = (item.findtext("description") or "").strip()
            items.append(
                {
                    "title": title,
                    "url": link,
                    "source": source,
                    "published_at": published,
                    "summary": description,
                }
            )
            if len(items) >= _MAX_ITEMS_PER_SYMBOL:
                break
        return items
    except Exception as exc:  # noqa: BLE001
        logger.warning("news fetch failed for %s: %s", query, exc)
        return []


def store_news(company_id: int, items: list[dict]) -> int:
    from sqlalchemy import select

    db = SessionLocal()
    count = 0
    try:
        for item in items:
            existing = db.execute(
                select(db_models.News).where(db_models.News.url == item["url"])
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(
                db_models.News(
                    company_id=company_id,
                    title=item["title"][:2000],
                    url=item["url"][:4000],
                    source=(item.get("source") or "Google News")[:64],
                    published_at=item.get("published_at"),
                    summary=(item.get("summary") or None),
                )
            )
            count += 1
        db.commit()
        return count
    finally:
        db.close()


async def sync_news(symbols: list[tuple[str, str]], names: dict[str, str]) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        for symbol, _ in symbols:
            if symbol == "IHSG":
                continue
            company_name = names.get(symbol, symbol)
            query = f"{symbol} saham {company_name.split(' PT ')[-1].replace(' Tbk', '')}"
            items = await fetch_news_rss(client, query)
            if not items:
                continue
            from sqlalchemy import select

            db = SessionLocal()
            company = db.execute(
                select(db_models.Company).where(db_models.Company.symbol == symbol)
            ).scalar_one_or_none()
            db.close()
            if not company:
                continue
            added = store_news(company.id, items)
            if added:
                logger.info("%s: %d news items added", symbol, added)