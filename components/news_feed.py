"""Right-panel news feed — aggregated news for all P123 tickers."""

import html
import urllib.parse

import streamlit as st

from services.news_data import fetch_multi_ticker_news
from utils.constants import COLORS_DARK, COLORS_LIGHT


def render_news_feed():
    """Render a scrollable news feed for every ticker in the P123 universe."""
    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # CSS scoping marker (same pattern as trader panel)
    st.markdown('<div class="news-feed-marker"></div>', unsafe_allow_html=True)

    st.markdown("#### News Feed")

    # Collect tickers from news_feed_tickers (filtered by settings checkboxes)
    nf_tickers = st.session_state.get("news_feed_tickers", set())
    if not nf_tickers:
        st.caption("No tickers enabled for news. Check Settings.")
        return

    all_tickers = sorted(
        t for t in nf_tickers if not t.startswith("^")
    )
    if not all_tickers:
        st.caption("No company tickers to fetch news for.")
        return

    # Header row: ticker count + refresh
    h1, h2 = st.columns([2, 1])
    with h1:
        st.caption(f"Watching **{len(all_tickers)}** tickers")
    with h2:
        if st.button("🔄", key="news_feed_refresh", use_container_width=True,
                      help="Refresh news"):
            # Clear the multi-ticker cache to force re-fetch
            fetch_multi_ticker_news.clear()
            st.rerun()

    # Fetch merged news
    config = st.session_state.get("config", {})
    per_ticker = config.get("settings", {}).get("news_feed_per_ticker", 3)
    total = config.get("settings", {}).get("news_feed_total", 30)

    news = fetch_multi_ticker_news(
        tuple(all_tickers), per_ticker=per_ticker, total=total
    )

    if not news:
        st.caption("No news articles found.")
        return

    # Build all items inside a wrapper <div> so Streamlit's markdown parser
    # treats it as a raw HTML block (inline <a> alone gets wrapped in <p>
    # and its block-level children are stripped).
    rows: list[str] = ['<div class="nf-list">']
    for item in news:
        title_escaped = html.escape(item["title"])
        source_escaped = html.escape(item.get("source", ""))
        summary = html.escape(item.get("summary", ""))
        if len(summary) > 120:
            summary = summary[:117] + "..."

        url = item.get("url", "")
        published = item.get("published", "")
        ticker = item.get("ticker", "")

        # Thumbnail or placeholder
        # NOTE: use <img> or <span> inside <a>, never <div>.
        # Streamlit's HTML sanitizer breaks <a> when it contains <div>.
        thumb_url = item.get("thumbnail_url")
        if thumb_url:
            thumb_html = (
                f'<img class="nf-thumb" src="{thumb_url}" '
                f'alt="" loading="lazy">'
            )
        else:
            thumb_html = ''

        # Ticker badge — links to in-app ticker page (not the news article)
        if ticker:
            ticker_url = f"?select={urllib.parse.quote(ticker)}&nf=1"
            badge_html = (
                f'<a href="{ticker_url}" class="nf-ticker" '
                f'target="_self">{html.escape(ticker)}</a>'
            )
        else:
            badge_html = ""

        # Meta line: ticker badge · source · time
        meta_parts = [badge_html] if badge_html else []
        if source_escaped:
            meta_parts.append(f'<span class="nf-source">{source_escaped}</span>')
        if published:
            meta_parts.append(f'<span class="nf-time">{published}</span>')
        meta_html = (
            f'<span class="nf-meta">{" &middot; ".join(meta_parts)}</span>'
        )

        # Summary
        summary_html = (
            f'<span class="nf-summary">{summary}</span>'
            if summary else ""
        )

        rows.append(
            f'<div class="nf-item">'
            f'{thumb_html}'
            f'<span class="nf-content">'
            f'{meta_html}'
            f'<a href="{url}" target="_blank" class="nf-title">{title_escaped}</a>'
            f'{summary_html}'
            f'</span>'
            f'</div>'
        )

    rows.append('</div>')
    st.markdown("\n".join(rows), unsafe_allow_html=True)
