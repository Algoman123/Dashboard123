"""Shared API key helpers — reads keys from .env file."""

import os
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def get_fred_key() -> str | None:
    """Return FRED API key or None if not set."""
    key = os.getenv("FRED_API_KEY", "")
    return key if key else None


def get_finnhub_key() -> str | None:
    """Return Finnhub API key or None if not set."""
    key = os.getenv("FINNHUB_API_KEY", "")
    return key if key else None


def get_alphavantage_key() -> str | None:
    """Return Alpha Vantage API key or None if not set."""
    key = os.getenv("ALPHAVANTAGE_KEY", "")
    return key if key else None


def get_fmp_key() -> str | None:
    """Return FMP API key or None if not set."""
    key = os.getenv("FMP_API_KEY", "")
    return key if key else None


def get_adanos_key() -> str | None:
    """Return Adanos Market Sentiment API key or None if not set."""
    key = os.getenv("ADANOS_API_KEY", "")
    return key if key else None
