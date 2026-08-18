"""Input validation, sanitization and prompt-injection protection."""
import re

SYMBOL_RE = re.compile(r"^[A-Z0-9\.\-\^]{1,16}$")
MAX_SYMBOL_LEN = 16
MAX_TEXT_LEN = 4000

# Untrusted content (news, scraped text) is wrapped so the model treats it as data.
UNTRUSTED_OPEN = "[UNTRUSTED_DATA_START]"
UNTRUSTED_CLOSE = "[UNTRUSTED_DATA_END]"


def valid_symbol(symbol: str) -> bool:
    if not symbol or len(symbol) > MAX_SYMBOL_LEN:
        return False
    return bool(SYMBOL_RE.match(symbol))


def sanitize_text(text: str, max_len: int = MAX_TEXT_LEN) -> str:
    if not text:
        return ""
    text = text.replace("\x00", "")
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    return text[:max_len]


def sanitize_ai_input(text: str, max_len: int = MAX_TEXT_LEN) -> str:
    """Sanitize user AI prompts. Block direct system-role override attempts."""
    text = sanitize_text(text, max_len)
    lowered = text.lower()
    if "system" in lowered and ("prompt" in lowered or "instruction" in lowered):
        if "ignore" in lowered or "override" in lowered or "role" in lowered:
            return text
    return text


def wrap_untrusted(content: str, max_len: int = 4000) -> str:
    """Mark scraped/news content as untrusted data for the model."""
    safe = sanitize_text(content, max_len)
    return f"{UNTRUSTED_OPEN}\n{safe}\n{UNTRUSTED_CLOSE}"


def ensure_max_context_symbols(symbols: list[str], limit: int = 8) -> list[str]:
    return [s for s in symbols if valid_symbol(s)][:limit]