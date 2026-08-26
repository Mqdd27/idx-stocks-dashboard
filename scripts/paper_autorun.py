"""Paper trading auto-run scheduler.

Runs the existing paper-trading engine once per trading day after market open.
Skips weekends and IDX holidays using the shared market calendar, so no trades
are created on non-trading days. Respects paper_bot_configs.enabled.
"""
import sys
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from collector.intraday import is_market_hours  # noqa: E402
from shared.common import get_logger, get_market_status, log_to_db, now_wib  # noqa: E402

logger = get_logger("paper-autorun")
settings = get_settings()


def main() -> int:
    now = now_wib()
    market = get_market_status(now)
    if not market.get("is_trading_day", False):
        logger.info("IDX non-trading day (%s); skipping autorun", market.get("status"))
        log_to_db("paper-autorun", "info", f"skipped: {market.get('status')}")
        return 0

    base = "http://127.0.0.1:8200"
    with httpx.Client(timeout=300) as client:
        config = client.get(f"{base}/api/paper-trading/config").json()
        if not config.get("enabled"):
            logger.info("paper bot disabled; skipping autorun")
            return 0
        resp = client.post(f"{base}/api/paper-trading/run")
        resp.raise_for_status()
        payload = resp.json()
    logger.info("autorun result: %s", payload)
    log_to_db("paper-autorun", "info", str(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
