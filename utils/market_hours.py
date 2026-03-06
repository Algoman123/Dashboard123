from datetime import datetime
from zoneinfo import ZoneInfo

# International (non-NA) suffixes — derived from chart.py's _YF_TO_TV mapping
_INTERNATIONAL_SUFFIXES = (
    ".ST", ".OL", ".HE", ".CO", ".DE", ".L", ".PA", ".AX", ".T",
    ".HK", ".SI", ".AS", ".BR", ".MC", ".MI", ".SW", ".VI",
    ".IR", ".LS", ".NZ", ".TA",
)

_ET = ZoneInfo("America/New_York")


def is_na_ticker(ticker: str) -> bool:
    """Return True if ticker is North American (US or Canadian)."""
    if ticker.startswith("^"):
        return True  # Index tickers like ^VIX
    for suffix in _INTERNATIONAL_SUFFIXES:
        if ticker.endswith(suffix):
            return False
    # US tickers have no suffix; Canadian (.TO, .V) are also NA
    return True


def is_na_market_active_today() -> bool:
    """True if NA markets have been open today (weekday and past 9:30 AM ET)."""
    now_et = datetime.now(_ET)
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    return now_et >= market_open


def filter_for_market_hours(tickers: list[str]) -> list[str]:
    """Remove NA tickers if their market hasn't opened today."""
    if is_na_market_active_today():
        return tickers
    return [t for t in tickers if not is_na_ticker(t)]
