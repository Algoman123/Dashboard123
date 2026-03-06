import pandas as pd
import streamlit as st
from utils.constants import TICKER_DISPLAY_NAMES, COLORS_DARK, COLORS_LIGHT
from utils.market_hours import filter_for_market_hours
from utils.p123_icon import P123_WAVE_SVG
from services.market_data import format_pct
from services.p123_client import p123_stock_url


def render_gainers_losers(n: int = 5):
    """Render top N gainers and top N losers from all loaded tickers."""
    market_data: pd.DataFrame = st.session_state.get("market_data", pd.DataFrame())
    if market_data.empty:
        return

    # Read count from settings (override default)
    config = st.session_state.get("config", {})
    n = config.get("settings", {}).get("movers_count", n)

    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # Filter for market hours (exclude NA tickers when markets are closed)
    eligible_tickers = filter_for_market_hours(list(market_data.index))
    if not eligible_tickers:
        return

    df = market_data.loc[market_data.index.isin(eligible_tickers)].copy()
    df = df.dropna(subset=["Daily"])
    if df.empty:
        return

    gainers = df.nlargest(n, "Daily")
    losers = df.nsmallest(n, "Daily")

    st.markdown('<div class="movers-section"></div>', unsafe_allow_html=True)
    col_gain, col_lose = st.columns(2)

    with col_gain:
        st.markdown(
            f'<div class="movers-header" style="color:{colors["green"]}">▲ Top Gainers</div>',
            unsafe_allow_html=True,
        )
        _render_mover_html(gainers, colors)

    with col_lose:
        st.markdown(
            f'<div class="movers-header" style="color:{colors["red"]}">▼ Top Losers</div>',
            unsafe_allow_html=True,
        )
        _render_mover_html(losers, colors)


def _render_mover_html(df: pd.DataFrame, colors: dict):
    """Render all mover rows as a single HTML block for perfect alignment."""
    rows = []
    for ticker in df.index:
        row = df.loc[ticker]
        display_name = TICKER_DISPLAY_NAMES.get(ticker, ticker)
        daily_val = row.get("Daily", 0)
        daily_str, _ = format_pct(daily_val)
        price = row.get("Price", 0)
        price_str = f"{price:,.2f}" if price < 10000 else f"{price:,.0f}"
        daily_color = colors["green"] if daily_val >= 0 else colors["red"]

        p123_link = p123_stock_url(ticker)
        icon_html = (
            f'<a href="{p123_link}" target="_blank" class="p123-link" '
            f'title="Open {ticker} on P123">{P123_WAVE_SVG}</a>'
            if p123_link
            else '<span class="p123-link">&nbsp;</span>'
        )

        ticker_html = (
            f'<a href="?select={ticker}" class="mover-ticker" '
            f'title="{display_name}">{ticker}</a>'
        )

        rows.append(
            f'<div class="mover-row">'
            f'{icon_html}'
            f'{ticker_html}'
            f'<span class="mover-price">{price_str}</span>'
            f'<span class="mover-change" style="color:{daily_color}">{daily_str}</span>'
            f'</div>'
        )

    st.markdown("\n".join(rows), unsafe_allow_html=True)
