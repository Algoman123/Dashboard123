"""Fetch and cache company news from Yahoo Finance via yfinance."""

from datetime import datetime, timezone

import streamlit as st
import yfinance as yf


def _parse_ts(iso_str: str) -> float:
    """Parse ISO 8601 string to UNIX timestamp (0.0 on failure)."""
    if not iso_str:
        return 0.0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def _time_ago(iso_str: str) -> str:
    """Convert ISO 8601 timestamp to human-friendly relative time."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return ""


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker_news(ticker: str, count: int = 8) -> list[dict]:
    """Fetch latest news for a ticker via yfinance.

    Returns a list of normalised dicts:
        title, url, source, published (relative), thumbnail_url, summary
    """
    # Skip index tickers — they have no company news page
    if ticker.startswith("^"):
        return []

    try:
        raw = yf.Ticker(ticker).get_news(count=count)
    except Exception:
        return []

    if not raw:
        return []

    results: list[dict] = []
    for item in raw:
        content = item.get("content", {})

        # Only include stories, skip videos
        if content.get("contentType") != "STORY":
            continue

        title = content.get("title", "")
        if not title:
            continue

        # Article URL
        url = ""
        canonical = content.get("canonicalUrl")
        if isinstance(canonical, dict):
            url = canonical.get("url", "")
        if not url:
            click = content.get("clickThroughUrl")
            if isinstance(click, dict):
                url = click.get("url", "")

        # Provider / source
        provider = content.get("provider", {})
        source = provider.get("displayName", "") if isinstance(provider, dict) else ""

        # Published time
        pub_date_raw = content.get("pubDate", "")
        published = _time_ago(pub_date_raw)
        sort_ts = _parse_ts(pub_date_raw)

        # Thumbnail — prefer the 170×128 size, fall back to original
        thumbnail_url = None
        thumb = content.get("thumbnail")
        if isinstance(thumb, dict):
            resolutions = thumb.get("resolutions") or []
            for res in resolutions:
                if isinstance(res, dict) and res.get("tag") == "170x128":
                    thumbnail_url = res.get("url")
                    break
            if not thumbnail_url and resolutions:
                # Fall back to first available resolution
                first = resolutions[0]
                if isinstance(first, dict):
                    thumbnail_url = first.get("url")

        # Summary snippet
        summary = content.get("summary", "") or ""

        results.append({
            "title": title,
            "url": url,
            "source": source,
            "published": published,
            "thumbnail_url": thumbnail_url,
            "summary": summary,
            "_sort_ts": sort_ts,
        })

    return results


@st.cache_data(ttl=900, show_spinner=False)
def fetch_multi_ticker_news(
    tickers: tuple[str, ...],
    per_ticker: int = 3,
    total: int = 30,
) -> list[dict]:
    """Fetch and merge news for multiple tickers, sorted newest-first.

    Each returned dict has an extra ``ticker`` field so the UI can badge it.
    *tickers* must be a **tuple** (hashable) for Streamlit caching.
    """
    merged: list[dict] = []
    for ticker in tickers:
        items = fetch_ticker_news(ticker, count=per_ticker)
        for item in items:
            merged.append({**item, "ticker": ticker})

    # Sort newest first by raw timestamp, then trim
    merged.sort(key=lambda x: x.get("_sort_ts", 0), reverse=True)
    return merged[:total]
