from collections import defaultdict

from sqlalchemy import desc, select

from .models import Company, ForeignFlowDaily

PERIODS = {"1d": 1, "5d": 5, "20d": 20, "1m": 22, "3m": 66}


def _status(net, ratio, streak):
    if net is None: return "NO DATA"
    if net > 0 and (ratio or 0) >= 10 and streak >= 3: return "STRONG ACCUMULATION"
    if net > 0: return "ACCUMULATION"
    if net < 0 and (ratio or 0) <= -10 and streak <= -3: return "STRONG DISTRIBUTION"
    if net < 0: return "DISTRIBUTION"
    return "NEUTRAL"


def _streak(rows):
    direction = count = 0
    for row in rows:
        net = row.net_foreign_volume or 0
        current = 1 if net > 0 else -1 if net < 0 else 0
        if not current or (direction and current != direction): break
        direction = current
        count += current
    return count


def _summary(rows, period):
    recent = rows[:PERIODS[period]]
    if not recent: return None
    buy = sum(row.foreign_buy_volume or 0 for row in recent)
    sell = sum(row.foreign_sell_volume or 0 for row in recent)
    net = buy - sell
    volume = sum(row.total_traded_volume or 0 for row in recent)
    ratio = net / volume * 100 if volume else None
    streak = _streak(rows)
    return {"trading_date": recent[0].trading_date, "foreign_buy_volume": buy, "foreign_sell_volume": sell, "net_foreign_volume": net, "total_traded_volume": volume, "net_foreign_ratio": ratio, "streak": streak, "status": _status(net, ratio, streak), "source": recent[0].source, "source_timestamp": recent[0].source_timestamp, "updated_at": recent[0].updated_at}


def _rows_by_symbol(db, limit=66):
    rows = db.execute(select(ForeignFlowDaily, Company.symbol).join(Company, Company.id == ForeignFlowDaily.company_id).order_by(Company.symbol, desc(ForeignFlowDaily.trading_date))).all()
    grouped = defaultdict(list)
    for row, symbol in rows:
        if len(grouped[symbol]) < limit: grouped[symbol].append(row)
    return grouped


def stock_flow(db, symbol, period="5d"):
    rows = _rows_by_symbol(db).get(symbol.upper(), [])
    if not rows: return {"symbol": symbol.upper(), "data": None, "history": []}
    result = _summary(rows, period)
    cumulative = 0
    history = []
    for row in reversed(rows):
        cumulative += row.net_foreign_volume or 0
        ratio = (row.net_foreign_volume or 0) / row.total_traded_volume * 100 if row.total_traded_volume else None
        history.append({"date": row.trading_date, "foreign_buy_volume": row.foreign_buy_volume, "foreign_sell_volume": row.foreign_sell_volume, "net_foreign_volume": row.net_foreign_volume, "cumulative_net_foreign_volume": cumulative, "total_traded_volume": row.total_traded_volume, "net_foreign_ratio": ratio})
    return {"symbol": symbol.upper(), "data": result, "history": list(reversed(history))}


def ranking(db, period="5d", direction="buy", limit=20):
    data = [{"symbol": symbol, **summary} for symbol, rows in _rows_by_symbol(db).items() if (summary := _summary(rows, period))]
    buying = direction == "buy"
    data = [item for item in data if item["net_foreign_volume"] > 0] if buying else [item for item in data if item["net_foreign_volume"] < 0]
    return sorted(data, key=lambda item: item["net_foreign_volume"], reverse=buying)[:limit]


def overview(db, period="5d"):
    buys = ranking(db, period, "buy", 20)
    sells = ranking(db, period, "sell", 20)
    return {"period": period, "data_type": "VOLUME_EOD", "top_buy": buys, "top_sell": sells, "market_date": buys[0]["trading_date"] if buys else sells[0]["trading_date"] if sells else None, "source": "IDX GetStockSummary"}
