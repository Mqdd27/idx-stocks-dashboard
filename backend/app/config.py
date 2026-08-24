import os
from pathlib import Path
from functools import lru_cache

try:
    from dotenv import load_dotenv

    load_dotenv("/etc/stocks-dashboard/backend.env", override=False)
    load_dotenv("/opt/stocks-dashboard/backend/.env.local", override=False)
except Exception:
    pass


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg2://stocks_app:stocks_app@127.0.0.1:5432/stocks",
        )
        self.nine_router_url: str = os.environ.get("NINE_ROUTER_URL", "http://127.0.0.1:20128/v1")
        self.nine_router_api_key: str = os.environ.get("NINE_ROUTER_API_KEY", "")
        self.ollama_url: str = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        self.default_ai_model: str = os.environ.get("DEFAULT_AI_MODEL", "qwen3.5:2b")
        self.market_poll_interval: int = int(os.environ.get("MARKET_POLL_INTERVAL", "30"))
        self.allow_ai_fallback: bool = os.environ.get("ALLOW_AI_FALLBACK", "false").lower() in ("1", "true", "yes")
        self.ai_rate_limit_per_minute: int = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", "20"))
        self.max_chat_length: int = int(os.environ.get("MAX_CHAT_LENGTH", "4000"))
        self.max_context_symbols: int = int(os.environ.get("MAX_CONTEXT_SYMBOLS", "8"))
        self.paper_candidates_limit: int = int(os.environ.get("PAPER_CANDIDATES_LIMIT", "280"))
        self.paper_candidates_cache_seconds: float = float(os.environ.get("PAPER_CANDIDATES_CACHE_SECONDS", "15"))
        self.paper_universe: tuple[str, ...] = tuple(
            symbol.strip().upper() for symbol in os.environ.get("PAPER_UNIVERSE", "").split(",") if symbol.strip()
        )
        self.timezone: str = os.environ.get("TZ", "Asia/Jakarta")
        self.log_dir: Path = Path(os.environ.get("LOG_DIR", "/opt/stocks-dashboard/logs"))


@lru_cache
def get_settings() -> Settings:
    return Settings()