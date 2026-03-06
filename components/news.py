"""Render Yahoo Finance-style news for the selected ticker."""

import html

import streamlit as st

from services.news_data import fetch_ticker_news
from utils.constants import COLORS_DARK, COLORS_LIGHT


def render_ticker_news(ticker: str, colors: dict):
    """Render latest news for *ticker* in a Yahoo Finance-inspired layout."""
    config = st.session_state.get("config", {})
    count = config.get("settings", {}).get("news_count", 6)

    news = fetch_ticker_news(ticker, count=max(count + 2, 8))
    if not news:
        return

    news = news[:count]

    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # Yahoo Finance link for the ticker
    yf_url = f"https://finance.yahoo.com/quote/{ticker}/news/"

    # Build header + all news items as a single HTML block (avoids CSS leak
    # from container-level selectors matching the entire page)
    header_html = (
        f'<div class="news-header">'
        f'<span>News</span>'
        f'<a href="{yf_url}" target="_blank" '
        f'class="news-header-link" title="View all on Yahoo Finance">'
        f'&#8599;</a>'
        f'</div>'
    )

    rows: list[str] = [header_html]
    for item in news:
        title_escaped = html.escape(item["title"])
        source_escaped = html.escape(item["source"])
        summary = html.escape(item.get("summary", ""))
        # Truncate summary
        if len(summary) > 140:
            summary = summary[:137] + "..."

        url = item.get("url", "")
        published = item.get("published", "")

        # Thumbnail or placeholder
        thumb_url = item.get("thumbnail_url")
        if thumb_url:
            thumb_html = (
                f'<img class="news-thumb" src="{thumb_url}" '
                f'alt="" loading="lazy">'
            )
        else:
            thumb_html = ''

        # Source + time line
        meta_parts = []
        if source_escaped:
            meta_parts.append(f'<span class="news-source">{source_escaped}</span>')
        if published:
            meta_parts.append(f'<span class="news-time">{published}</span>')
        meta_html = (
            f'<div class="news-meta">{" &middot; ".join(meta_parts)}</div>'
        )

        # Summary line
        summary_html = (
            f'<div class="news-summary">{summary}</div>'
            if summary else ""
        )

        rows.append(
            f'<a href="{url}" target="_blank" class="news-item">'
            f'{thumb_html}'
            f'<div class="news-content">'
            f'{meta_html}'
            f'<div class="news-title">{title_escaped}</div>'
            f'{summary_html}'
            f'</div>'
            f'</a>'
        )

    st.markdown("\n".join(rows), unsafe_allow_html=True)
