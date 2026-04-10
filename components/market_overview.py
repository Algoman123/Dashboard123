import yfinance as yf
import streamlit as st
from services.market_data import fetch_market_data, format_pct
from utils.constants import OVERVIEW_TICKERS, TICKER_DISPLAY_NAMES, COLORS_DARK, COLORS_LIGHT

# Sparkline period -> yfinance params mapping
SPARKLINE_PARAMS = {
    "1d": {"period": "1d", "interval": "5m"},
    "5d": {"period": "5d", "interval": "30m"},
    "1mo": {"period": "1mo", "interval": "1d"},
    "3mo": {"period": "3mo", "interval": "1d"},
    "1y": {"period": "1y", "interval": "1wk"},
}


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_sparkline_data(ticker: str, period: str, interval: str) -> list[float]:
    """Fetch price data for sparkline chart."""
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True, timeout=30)
        if data.empty:
            return []
        close = data["Close"].dropna()
        if hasattr(close, "values"):
            return [float(v) for v in close.values.flatten()[-60:]]
        return []
    except Exception:
        return []


def _svg_sparkline(values: list[float], color: str, width: int = 100, height: int = 28) -> str:
    """Generate a tiny SVG sparkline from price values."""
    if len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    points = []
    for i, v in enumerate(values):
        x = round(i / (len(values) - 1) * width, 1)
        y = round(height - (v - mn) / rng * (height - 2) - 1, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;margin:4px auto 0;">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def get_overview_tickers() -> list[str]:
    """Get overview tickers from config, falling back to constant."""
    config = st.session_state.get("config", {})
    return config.get("settings", {}).get("overview_tickers", OVERVIEW_TICKERS)


def render_market_overview():
    """Render market overview mini-cards with sparklines."""
    overview_tickers = get_overview_tickers()
    if not overview_tickers:
        return

    data = fetch_market_data(tuple(overview_tickers))
    if data.empty:
        return

    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # Get sparkline period from config
    config = st.session_state.get("config", {})
    spark_period_key = config.get("settings", {}).get("sparkline_period", "5d")
    spark_params = SPARKLINE_PARAMS.get(spark_period_key, SPARKLINE_PARAMS["5d"])

    cols = st.columns(len(overview_tickers))
    for i, ticker in enumerate(overview_tickers):
        with cols[i]:
            if ticker in data.index:
                row = data.loc[ticker]
                price = row.get("Price", 0)
                daily = row.get("Daily", 0) or 0
                name = TICKER_DISPLAY_NAMES.get(ticker, ticker)
                change_str, css_class = format_pct(daily)
                spark_color = colors["green"] if daily >= 0 else colors["red"]

                if price > 1000:
                    price_str = f"{price:,.0f}"
                else:
                    price_str = f"{price:,.2f}"

                spark_values = _fetch_sparkline_data(
                    ticker, spark_params["period"], spark_params["interval"]
                )
                sparkline_svg = _svg_sparkline(spark_values, spark_color)

                st.markdown(
                    f"""<div class="metric-card">
                        <div class="label">{name}</div>
                        <div class="price">{price_str}</div>
                        <div class="change {css_class}">{change_str}</div>
                        {sparkline_svg}
                    </div>""",
                    unsafe_allow_html=True,
                )
