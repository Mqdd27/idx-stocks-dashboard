from datetime import datetime
import hashlib
from pathlib import Path
import subprocess
from sqlalchemy import desc, select

from app.db import SessionLocal
from app.market_calendar import TZ, get_market_status, next_trading_day
from app.recommendation_model import TradeRecommendation
from app.watchlist_model import AIWatchlist
from app.telegram_delivery_model import TelegramDelivery
from PIL import Image, ImageDraw, ImageFont


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



def _records(strategy):
    with SessionLocal() as db:
        recs = db.execute(select(TradeRecommendation).where(TradeRecommendation.strategy == strategy).order_by(desc(TradeRecommendation.trading_date), desc(TradeRecommendation.generated_at), desc(TradeRecommendation.id))).scalars().all()
    paper = _latest([row for row in recs if row.method == "PAPER_TRADE" and row.action == "BUY"])
    agents = _latest([row for row in recs if row.method == "TRADING_AGENTS" and row.action == "BUY"])
    latest_date = max([row.trading_date for row in paper + agents], default=datetime.now(TZ).date())
    return latest_date, [row for row in agents if row.trading_date == latest_date], [row for row in paper if row.trading_date == latest_date]


def render_report_image(strategy, path=None):
    trading_date, agents, paper = _records(strategy)
    rows = [("TRADINGAGENTS", row) for row in agents[:5]] + [("PAPER ENGINE", row) for row in paper[:5]]
    width, row_h = 1400, 68
    height = 260 + max(1, len(rows)) * row_h + 100
    image = Image.new("RGB", (width, height), "#080b12")
    draw = ImageDraw.Draw(image)
    regular = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 25)
    title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 19)
    amber, text, muted, green, red, border = "#f6a623", "#e8ecf4", "#7d879c", "#00c176", "#ff4d5e", "#273149"
    draw.rectangle((0, 0, width, 8), fill=amber)
    draw.text((42, 34), f"STX STOCKS IDX · {strategy}", font=title, fill=text)
    draw.text((42, 90), f"REKOMENDASI SAHAM · {trading_date.strftime('%d %b %Y')}", font=bold, fill=amber)
    draw.text((42, 130), "Source separated: TradingAgents / Paper Trade Quant Engine", font=small, fill=muted)
    columns = [(42, "SOURCE"), (245, "CODE"), (365, "ENTRY ZONE"), (575, "TP1 / TP2"), (785, "STOP LOSS"), (955, "R/R"), (1065, "SCORE / CONF"), (1260, "STATUS")]
    y = 190
    draw.rectangle((30, y, width - 30, y + 48), fill="#11172a", outline=border)
    for x, label in columns:
        draw.text((x, y + 11), label, font=small, fill=muted)
    y += 48
    if not rows:
        draw.text((42, y + 24), "NO QUALIFIED SETUP", font=bold, fill=red)
    for source, row in rows:
        draw.rectangle((30, y, width - 30, y + row_h), fill="#0d121d", outline=border)
        color = amber if source == "TRADINGAGENTS" else "#3e9cff"
        values = [source, row.symbol, f"{_price(row.entry_low)}-{_price(row.entry_high)}", f"{_price(row.tp1)} / {_price(row.tp2)}", _price(row.stop_loss), f"{float(row.risk_reward or 0):.2f}", row.confidence_label if source == "TRADINGAGENTS" else str(row.score or "-"), row.status]
        for (x, _), value in zip(columns, values):
            draw.text((x, y + 18), str(value), font=bold if value == row.symbol else regular, fill=color if value in (source, row.symbol) else text)
        y += row_h
    draw.text((42, height - 65), "Research / paper trading only · No guaranteed profit · No brokerage order", font=small, fill=muted)
    output = path or f"/tmp/{strategy.lower()}-recommendations.png"
    image.save(output, "PNG", optimize=True)
    return output


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
    target_date = next_trading_day(datetime.now(TZ).date())
    content_hash = hashlib.sha256(message.encode()).hexdigest()
    with SessionLocal() as db:
        delivery = db.execute(select(TelegramDelivery).where(TelegramDelivery.message_type == "recommendation", TelegramDelivery.target_date == target_date, TelegramDelivery.cycle == strategy).with_for_update()).scalar_one_or_none()
        if delivery and delivery.status == "SENT" and delivery.content_hash == content_hash:
            return 0
        if not delivery:
            delivery = TelegramDelivery(message_type="recommendation", target_date=target_date, cycle=strategy, content_hash=content_hash)
            db.add(delivery)
        delivery.content_hash = content_hash
        delivery.status = "SENDING"
        delivery.attempt_count += 1
        db.commit()
    try:
        image_path = render_report_image(strategy)
        media_result = subprocess.run(["/home/mqdd/.local/bin/hermes", "send", "--to", "telegram", f"MEDIA:{image_path}"], check=False, timeout=60)
        text_result = subprocess.run(["/home/mqdd/.local/bin/hermes", "send", "--to", "telegram", message], check=False, timeout=45)
        ok = media_result.returncode == 0 and text_result.returncode == 0
        error = None if ok else f"media={media_result.returncode},text={text_result.returncode}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        ok, error = False, str(exc)[:500]
    with SessionLocal() as db:
        delivery = db.execute(select(TelegramDelivery).where(TelegramDelivery.message_type == "recommendation", TelegramDelivery.target_date == target_date, TelegramDelivery.cycle == strategy).with_for_update()).scalar_one(); delivery.status = "SENT" if ok else "FAILED"; delivery.last_error = error; delivery.sent_at = datetime.now(TZ) if ok else None; db.commit(); return 0 if ok else 1
