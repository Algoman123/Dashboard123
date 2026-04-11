"""Market Sentiment Dashboard — Fear & Greed, breadth, AAII, social mentions."""

import altair as alt
import pandas as pd
import streamlit as st

from services.sentiment_data import (
    fetch_fear_greed,
    fetch_fear_greed_history,
    fetch_breadth_data,
    fetch_aaii_sentiment,
    fetch_adanos_sentiment,
    download_aaii_xls,
)
from services.api_keys import get_adanos_key


def render_sentiment_dashboard(colors: dict, theme: str):
    """Render the full sentiment dashboard, replacing the normal main content."""

    # Header with refresh button
    hdr_left, hdr_center, hdr_right = st.columns([1, 6, 1])
    with hdr_center:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 10px 0 4px 0;">
                <div style="font-size:28px; font-weight:700; color:{colors['text_header']};">
                    Market Sentiment
                </div>
                <div style="font-size:13px; color:{colors['text_muted']};">
                    Fear &amp; Greed, market breadth, investor surveys &amp; social mentions
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_right:
        if st.button("🔄", key="refresh_sentiment", help="Refresh sentiment data"):
            fetch_fear_greed.clear()
            fetch_fear_greed_history.clear()
            fetch_breadth_data.clear()
            fetch_aaii_sentiment.clear()
            fetch_adanos_sentiment.clear()
            st.rerun()

    tab_fg, tab_br, tab_aaii, tab_adanos = st.tabs([
        "Fear & Greed", "Market Breadth", "AAII Survey", "Adanos Sentiment",
    ])

    with tab_fg:
        _render_fear_greed_tab(colors, theme)

    with tab_br:
        _render_breadth_tab(colors, theme)

    with tab_aaii:
        _render_aaii_tab(colors, theme)

    with tab_adanos:
        _render_adanos_tab(colors, theme)


# ---------------------------------------------------------------------------
# Shared chart helpers
# ---------------------------------------------------------------------------

def _style_chart(chart, colors: dict, height: int = 280):
    """Apply dark/light theme styling to an Altair chart."""
    return (
        chart
        .properties(height=height)
        .configure_view(strokeWidth=0)
        .configure(background=colors["bg_card"])
        .configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            gridColor=f"{colors['border']}33",
            domainColor=colors["border"],
        )
        .configure_legend(
            labelColor=colors["text"],
            titleColor=colors["text"],
        )
    )


def _parse_adanos_ticker_input(value: str) -> tuple[str, ...]:
    """Parse comma or whitespace-separated tickers for the Adanos tab."""
    tickers: list[str] = []
    seen: set[str] = set()
    for token in str(value or "").replace(",", " ").split():
        ticker = token.strip().upper().replace("$", "")
        if not ticker or ticker.startswith("^") or "=" in ticker or ticker.endswith("-USD"):
            continue
        if ticker in seen:
            continue
        tickers.append(ticker)
        seen.add(ticker)
        if len(tickers) >= 10:
            break
    return tuple(tickers)


def _default_adanos_tickers() -> str:
    """Seed the Adanos tab from the active ticker/watchlist when available."""
    candidates: list[str] = []

    selected_ticker = st.session_state.get("selected_ticker")
    if selected_ticker:
        candidates.append(selected_ticker)

    feed_tickers = st.session_state.get("news_feed_tickers")
    if isinstance(feed_tickers, str):
        candidates.extend(feed_tickers.replace(",", " ").split())
    elif isinstance(feed_tickers, (list, tuple, set)):
        candidates.extend(feed_tickers)

    normalized: list[str] = []
    seen: set[str] = set()
    for ticker in candidates:
        value = str(ticker or "").strip().upper().replace("$", "")
        if not value or value.startswith("^") or "=" in value or value.endswith("-USD") or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
        if len(normalized) >= 5:
            break

    return ", ".join(normalized) if normalized else "SPY, QQQ, TSLA, NVDA, AAPL"


def _render_adanos_tab(colors: dict, theme: str):
    """Optional Adanos Market Sentiment API enrichment."""
    st.markdown(
        f"""
        <div class="factor-card" style="padding:14px; margin-bottom:12px;">
            <div style="font-size:15px; font-weight:600; color:{colors['text_header']}; margin-bottom:4px;">
                Optional Adanos Market Sentiment
            </div>
            <div style="font-size:12px; color:{colors['text_muted']}; line-height:1.6;">
                Adds authenticated watchlist sentiment from Reddit, X/Twitter, news, and Polymarket.
                No Adanos request is made unless <code>ADANOS_API_KEY</code> is configured.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    input_col, days_col = st.columns([4, 1])
    with input_col:
        ticker_input = st.text_input(
            "Tickers",
            value=_default_adanos_tickers(),
            key="adanos_sentiment_tickers",
            help="Comma or space-separated symbols. Adanos compare endpoints support up to 10 tickers.",
        )
    with days_col:
        days = st.slider("Days", 1, 90, 30, 1, key="adanos_sentiment_days")

    tickers = _parse_adanos_ticker_input(ticker_input)
    if not tickers:
        st.info("Enter at least one stock ticker to load Adanos sentiment.")
        return

    if not get_adanos_key():
        st.info(
            "Set ADANOS_API_KEY in your .env file to enable this optional sentiment source. "
            "Until then, the dashboard skips Adanos network calls."
        )
        return

    df = fetch_adanos_sentiment(tickers, days=days)
    if df.empty:
        st.warning("No Adanos sentiment data returned for the selected tickers and lookback.")
        return

    buzz = pd.to_numeric(df.get("Buzz Score", pd.Series(dtype=float)), errors="coerce")
    sentiment = pd.to_numeric(df.get("Sentiment Score", pd.Series(dtype=float)), errors="coerce")
    top_row = df.iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Tickers", df["Ticker"].nunique())
    with k2:
        st.metric("Avg Buzz", f"{buzz.mean():.1f}" if buzz.notna().any() else "N/A")
    with k3:
        st.metric("Avg Sentiment", f"{sentiment.mean():+.2f}" if sentiment.notna().any() else "N/A")
    with k4:
        st.metric("Top Signal", top_row["Ticker"], top_row["Platform"])

    display_columns = [
        "Platform",
        "Ticker",
        "Company",
        "Buzz Score",
        "Sentiment Score",
        "Bullish %",
        "Bearish %",
        "Mentions",
        "Source Count",
        "Trade Count",
        "Liquidity",
        "Trend",
    ]
    present_columns = [column for column in display_columns if column in df.columns]
    st.dataframe(df[present_columns], use_container_width=True, hide_index=True)

    chart_df = df.dropna(subset=["Buzz Score"]).copy()
    if not chart_df.empty:
        chart_df["Signal"] = chart_df["Ticker"] + " / " + chart_df["Platform"]
        chart = (
            alt.Chart(chart_df)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("Buzz Score:Q", title="Buzz Score", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Signal:N", title=None, sort="-x"),
                color=alt.Color("Platform:N", legend=alt.Legend(orient="top", title=None)),
                tooltip=[
                    "Platform:N",
                    "Ticker:N",
                    alt.Tooltip("Buzz Score:Q", format=".1f"),
                    alt.Tooltip("Sentiment Score:Q", format="+.2f"),
                    alt.Tooltip("Bullish %:Q", format=".0f"),
                    alt.Tooltip("Bearish %:Q", format=".0f"),
                    "Trend:N",
                ],
            )
        )
        st.altair_chart(_style_chart(chart, colors, 300), use_container_width=True)

    st.caption(
        "Adanos data is optional and fetched only with ADANOS_API_KEY. "
        "Use it to enrich Dashboard123 watchlists with cross-platform retail and market sentiment."
    )


# ---------------------------------------------------------------------------
# Tab 1: Fear & Greed
# ---------------------------------------------------------------------------

def _render_fear_greed_tab(colors: dict, theme: str):
    """CNN Fear & Greed composite index."""

    data = fetch_fear_greed()
    if not data:
        st.warning("Unable to fetch Fear & Greed data. Try again later.")
        return

    score = data.get("score", 0)
    rating = data.get("rating", "unknown")
    indicators = data.get("indicators", {})
    history = data.get("history", {})

    # Score color
    if score <= 25:
        score_color = colors["red"]
        label = "Extreme Fear"
    elif score <= 45:
        score_color = "#E8A838"
        label = "Fear"
    elif score <= 55:
        score_color = colors["text_muted"]
        label = "Neutral"
    elif score <= 75:
        score_color = "#8BC34A"
        label = "Greed"
    else:
        score_color = colors["green"]
        label = "Extreme Greed"

    # Large score display
    st.markdown(
        f"""
        <div class="factor-card" style="text-align:center; padding:20px;">
            <div style="font-size:14px; color:{colors['text_muted']}; text-transform:uppercase; letter-spacing:1px;">
                CNN Fear &amp; Greed Index
            </div>
            <div style="font-size:64px; font-weight:800; color:{score_color}; margin:8px 0;">
                {score:.0f}
            </div>
            <div style="font-size:22px; font-weight:600; color:{score_color};">
                {label}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Gauge bar
    gauge_pct = min(100, max(0, score))
    st.markdown(
        f"""
        <div style="margin:8px auto 16px auto; max-width:600px;">
            <div style="height:16px; border-radius:8px; background:linear-gradient(to right,
                {colors['red']}, #E8A838, {colors['text_muted']}, #8BC34A, {colors['green']});
                position:relative; overflow:visible;">
                <div style="position:absolute; left:{gauge_pct}%; top:-4px;
                    width:4px; height:24px; background:{colors['text_header']}; border-radius:2px;
                    transform:translateX(-2px);"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:{colors['text_muted']}; margin-top:4px;">
                <span>Extreme Fear</span><span>Fear</span><span>Neutral</span><span>Greed</span><span>Extreme Greed</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # History comparison
    if history:
        hist_cols = st.columns(5)
        periods = [("1w", "1 Week Ago"), ("1m", "1 Month Ago"), ("3m", "3 Months Ago"),
                   ("6m", "6 Months Ago"), ("1y", "1 Year Ago")]
        for i, (key, label_text) in enumerate(periods):
            val = history.get(key)
            if val is not None:
                diff = score - val
                diff_color = colors["green"] if diff > 0 else colors["red"] if diff < 0 else colors["text_muted"]
                with hist_cols[i]:
                    st.markdown(
                        f"""
                        <div class="factor-card" style="text-align:center; padding:8px 4px;">
                            <div style="font-size:10px; color:{colors['text_muted']};">{label_text}</div>
                            <div style="font-size:20px; font-weight:700; color:{colors['text']};">{val:.0f}</div>
                            <div style="font-size:11px; color:{diff_color};">{diff:+.0f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # Component breakdown
    if indicators:
        st.markdown(
            f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 8px 0;">'
            f'Component Breakdown</div>',
            unsafe_allow_html=True,
        )

        _INDICATOR_LABELS = {
            "market_momentum_sp500": "Market Momentum (S&P 500)",
            "stock_price_strength": "Stock Price Strength",
            "stock_price_breadth": "Stock Price Breadth",
            "put_call_options": "Put/Call Options",
            "market_volatility_vix": "Market Volatility (VIX)",
            "junk_bond_demand": "Junk Bond Demand",
            "safe_haven_demand": "Safe Haven Demand",
        }

        for key, info in indicators.items():
            ind_score = info.get("score", 0)
            ind_rating = info.get("rating", "")
            ind_label = _INDICATOR_LABELS.get(key, key.replace("_", " ").title())

            # Bar color
            if ind_score <= 25:
                bar_color = colors["red"]
            elif ind_score <= 45:
                bar_color = "#E8A838"
            elif ind_score <= 55:
                bar_color = colors["text_muted"]
            elif ind_score <= 75:
                bar_color = "#8BC34A"
            else:
                bar_color = colors["green"]

            st.markdown(
                f"""
                <div style="margin:6px 0;">
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
                        <span style="color:{colors['text']};">{ind_label}</span>
                        <span style="color:{bar_color}; font-weight:600;">{ind_score:.0f} — {ind_rating}</span>
                    </div>
                    <div style="height:8px; border-radius:4px; background:{colors['border']}33;">
                        <div style="width:{min(100, ind_score)}%; height:100%; border-radius:4px; background:{bar_color};"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Historical chart
    hist_df = fetch_fear_greed_history()
    if not hist_df.empty:
        st.markdown(
            f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 4px 0;">'
            f'Fear &amp; Greed — {len(hist_df)} Trading Days</div>',
            unsafe_allow_html=True,
        )

        _fg_y_scale = alt.Scale(domain=[0, 100])

        # Build score line + zones + refs on same y scale
        score_line = (
            alt.Chart(hist_df)
            .mark_line(strokeWidth=2, color="#3D85C6")
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                y=alt.Y("Score:Q", title="Fear & Greed Score", scale=_fg_y_scale),
                tooltip=[alt.Tooltip("Score:Q", format=".0f"), "Rating:N", "Date:T"],
            )
        )

        # Embed reference lines as data points in the score DataFrame
        ref_data = pd.DataFrame([
            {"Date": hist_df["Date"].min(), "Level": 25, "Label": "Extreme Fear"},
            {"Date": hist_df["Date"].max(), "Level": 25, "Label": "Extreme Fear"},
            {"Date": hist_df["Date"].min(), "Level": 75, "Label": "Extreme Greed"},
            {"Date": hist_df["Date"].max(), "Level": 75, "Label": "Extreme Greed"},
        ])

        ref_25 = (
            alt.Chart(ref_data[ref_data["Level"] == 25])
            .mark_line(strokeDash=[4, 4], strokeWidth=1, color=colors["red"])
            .encode(x="Date:T", y=alt.Y("Level:Q", scale=_fg_y_scale))
        )
        ref_75 = (
            alt.Chart(ref_data[ref_data["Level"] == 75])
            .mark_line(strokeDash=[4, 4], strokeWidth=1, color=colors["green"])
            .encode(x="Date:T", y=alt.Y("Level:Q", scale=_fg_y_scale))
        )

        # SPY overlay on right y-axis
        d_min = hist_df["Date"].min().strftime("%Y-%m-%d")
        spy_df = _fetch_spy_overlay(d_min)

        if spy_df is not None:
            spy_line = (
                alt.Chart(spy_df)
                .mark_line(strokeWidth=1, opacity=0.4, color=colors["green"])
                .encode(
                    x="Date:T",
                    y=alt.Y("SPY:Q", title="SPY", axis=alt.Axis(orient="right")),
                    tooltip=[alt.Tooltip("SPY:Q", format=",.0f"), "Date:T"],
                )
            )
            # Layer: score-axis layers first, then SPY independently
            score_layers = ref_25 + ref_75 + score_line
            chart = alt.layer(score_layers, spy_line).resolve_scale(y="independent")
        else:
            chart = ref_25 + ref_75 + score_line

        st.altair_chart(_style_chart(chart, colors, 300), width="stretch")

    st.caption(
        "Extreme Fear readings have historically been contrarian buy signals. "
        "Extreme Greed often precedes corrections. Data from CNN Business Fear & Greed Index. "
        "Historical data: github.com/jasonisdoing/fear-and-greed."
    )

    # ---- Backtester ----
    if not hist_df.empty:
        _render_fg_backtest(hist_df, colors, theme)


@st.cache_data(ttl=43200, show_spinner=False)
def _fetch_spy_overlay(start: str) -> pd.DataFrame | None:
    """Fetch SPY price data for chart overlay."""
    try:
        import yfinance as yf
        spy = yf.download("SPY", start=start, auto_adjust=True,
                          progress=False, timeout=30)
        if spy.empty:
            return None
        spy_close = spy["Close"]
        if hasattr(spy_close, "columns"):
            spy_close = spy_close.iloc[:, 0]
        spy_df = pd.DataFrame({"Date": spy_close.index, "SPY": spy_close.values})
        spy_df["Date"] = pd.to_datetime(spy_df["Date"]).dt.tz_localize(None)
        return spy_df
    except Exception:
        return None


@st.cache_data(ttl=43200, show_spinner=False)
def _fetch_etf_for_backtest(ticker: str, start: str) -> pd.Series:
    """Fetch daily close for a ticker."""
    try:
        import yfinance as yf
        data = yf.download(ticker, start=start, auto_adjust=True,
                           progress=False, timeout=30)
        if data.empty:
            return pd.Series(dtype=float)
        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        close.index = pd.to_datetime(close.index).tz_localize(None)
        return close
    except Exception:
        return pd.Series(dtype=float)


def _render_fg_backtest(hist_df: pd.DataFrame, colors: dict, theme: str):
    """Fear & Greed backtest — multiple strategies with daily equity curves."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Fear &amp; Greed Backtester</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Strategy Descriptions", expanded=False):
        st.markdown(
            f"""
            <div style="color:{colors['text']}; font-size:12px; line-height:1.7;">
            <p><b>Contrarian (buy fear, sell greed)</b> — Buy when F&amp;G drops below the buy level,
            sell when it rises above the sell level. Classic Buffett: "be greedy when others are fearful."
            <i>Example: Buy below 25, sell above 75. F&amp;G hits 20 → BUY. Rises to 80 → SELL.</i></p>

            <p><b>ETF Rotation (risk-on / risk-off)</b> — Always invested, never in cash.
            Hold risk ETF when F&amp;G is above threshold, automatically switch to defensive ETF when below.
            Single threshold — no gap.
            <i>Example: Threshold 50, SPY/TLT. F&amp;G at 60 → hold SPY. Drops to 40 → switch to TLT.</i></p>

            <p><b>Buy fear &amp; wait N days</b> — Buy when F&amp;G drops below threshold, hold for exactly
            N trading days regardless of what happens to sentiment. Tests if buying fear is profitable
            over a fixed horizon.
            <i>Example: Buy below 20, hold 30 days. F&amp;G hits 18 → BUY. Hold for 30 days → SELL regardless.</i></p>

            <p><b>Momentum (follow trend)</b> — Buy when F&amp;G rises above the buy level, sell when it
            drops below the sell level. Follows the sentiment trend — ride greed, exit when fear returns.
            Can re-enter immediately if F&amp;G bounces back.
            <i>Example: Buy above 50, sell below 40. F&amp;G at 55 → BUY. Drops to 35 → SELL. Rises to 52 → BUY again.</i></p>

            <p><b>Momentum confirmed (fear→greed cross)</b> — Like momentum but requires F&amp;G to have
            first been <b>below</b> the buy level before crossing above it. Filters out noise — only enters
            when there's a genuine shift from fear to greed. More selective, fewer trades.
            <i>Example: Buy above 50, sell below 40. F&amp;G at 30 (below 50 ✓). Rises to 55 → BUY (confirmed cross).
            Drops to 35 → SELL. F&amp;G at 45 → rises to 55 → NO BUY (never went below 50). F&amp;G drops to 48 (below 50 ✓).
            Rises to 55 → BUY (confirmed cross).</i></p>

            <p><b>Band (risk-on between levels)</b> — Always invested. Hold risk ETF when F&amp;G is
            between the two levels, switch to defensive ETF when outside (both extreme fear AND extreme greed
            are risk-off). Useful for avoiding both panics and euphoric tops.
            <i>Example: Band 25-75, SPY/TLT. F&amp;G at 50 → hold SPY. Drops to 15 → switch to TLT.
            Rises to 30 → back to SPY. Rises to 80 → switch to TLT (greed too extreme).</i></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _STRATEGIES = [
        "Contrarian (buy fear, sell greed)",
        "ETF Rotation (risk-on / risk-off)",
        "Buy fear & wait N days",
        "Momentum (follow trend)",
        "Momentum confirmed (fear→greed cross)",
        "Band (risk-on between levels)",
    ]

    # Controls
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        strategy = st.selectbox("Strategy", _STRATEGIES, key="fg_bt_strategy")
    with col_s2:
        etf = st.selectbox("Risk-on ETF", ["SPY", "QQQ", "IWM", "TLT", "GLD", "SH"], key="fg_bt_etf")

    col_s3, col_s4, col_s5 = st.columns(3)
    is_band = "band" in strategy.lower()
    is_rotation = "rotation" in strategy.lower()
    is_momentum = "momentum" in strategy.lower() and "confirmed" not in strategy.lower()
    is_confirmed = "confirmed" in strategy.lower()
    is_wait = "wait" in strategy.lower()

    with col_s3:
        if is_momentum or is_confirmed:
            buy_level = st.slider("Buy above", 0, 100, 50, 5, key="fg_bt_buy",
                                  help="Enter when F&G rises above this level")
        elif is_rotation:
            buy_level = st.slider("Switch to risk-on above", 0, 100, 50, 5, key="fg_bt_buy",
                                  help="Hold risk ETF when F&G is above this level")
        elif is_band:
            buy_level = st.slider("Risk-on above (fear exit)", 0, 100, 25, 5, key="fg_bt_buy",
                                  help="Switch to risk-on when F&G rises above this level")
        else:
            buy_level = st.slider("Buy below", 0, 100, 25, 5, key="fg_bt_buy",
                                  help="Enter when F&G drops below this level")
    with col_s4:
        if is_wait:
            hold_days = st.slider("Hold days", 5, 120, 30, 5, key="fg_bt_hold")
            sell_level = 100
        elif is_momentum or is_confirmed:
            sell_level = st.slider("Sell below", 0, 100, 40, 5, key="fg_bt_sell_mom",
                                   help="Exit when F&G drops below this level")
            hold_days = 0
        elif is_rotation:
            sell_level = buy_level
            hold_days = 0
            defensive_etf = st.selectbox("Risk-off ETF",
                                          ["Cash", "TLT", "GLD", "SHY", "IEF", "SH"],
                                          key="fg_bt_def_etf",
                                          help="Hold this ETF during fear periods")
        elif is_band:
            sell_level = st.slider("Risk-off above (greed exit)", 0, 100, 75, 5, key="fg_bt_sell_band",
                                   help="Switch to risk-off when F&G rises above this level")
            hold_days = 0
        else:  # Contrarian
            sell_level = st.slider("Sell above", 0, 100, 75, 5, key="fg_bt_sell",
                                   help="Exit when F&G rises above this level")
            hold_days = 0
    with col_s5:
        if is_rotation:
            st.caption(f"Always invested: {etf} ↔ {defensive_etf}")
            cash_etf = "rotation"
        elif is_band:
            defensive_etf = st.selectbox("Risk-off ETF",
                                          ["Cash", "TLT", "GLD", "SHY", "IEF", "SH"],
                                          key="fg_bt_def_etf_band",
                                          help="Hold when outside the band")
            st.caption(f"Risk-on ({buy_level}–{sell_level}): {etf}")
            st.caption(f"Risk-off (<{buy_level} or >{sell_level}): {defensive_etf}")
            cash_etf = "band"
        else:
            cash_etf = st.selectbox("When out of market, hold:",
                                    ["Cash (0%)", "TLT (bonds)", "GLD (gold)", "SHY (short-term)", "SH (short SPY)"],
                                    key="fg_bt_cash")

    # Fetch ETF data
    d_min = hist_df["Date"].min().strftime("%Y-%m-%d")
    etf_prices = _fetch_etf_for_backtest(etf, d_min)

    if etf_prices.empty:
        st.warning(f"Unable to fetch {etf} data for backtest.")
        return

    # Fetch cash/defensive alternative ETF
    cash_ticker = None
    cash_prices = pd.Series(dtype=float)
    if is_rotation or is_band:
        cash_ticker = defensive_etf if defensive_etf != "Cash" else None
    else:
        if "TLT" in cash_etf:
            cash_ticker = "TLT"
        elif "GLD" in cash_etf:
            cash_ticker = "GLD"
        elif "SHY" in cash_etf:
            cash_ticker = "SHY"
        elif "SH" in cash_etf:
            cash_ticker = "SH"
    if cash_ticker and cash_ticker != "Cash" and cash_ticker != etf:
        cash_prices = _fetch_etf_for_backtest(cash_ticker, d_min)

    # Align F&G scores with ETF prices
    fg_series = hist_df.set_index("Date")["Score"]
    fg_series.index = pd.to_datetime(fg_series.index)
    aligned = pd.DataFrame({"FG": fg_series, "Price": etf_prices})
    if not cash_prices.empty:
        aligned["CashPrice"] = cash_prices
    aligned = aligned.dropna(subset=["FG", "Price"])

    if len(aligned) < 50:
        st.warning("Not enough overlapping data for backtest.")
        return

    # ---- Run daily equity curve backtest ----
    equity_values = []
    current_equity = 10000.0
    in_position = False
    entry_price = None
    shares = 0.0
    hold_counter = 0
    cash_shares = 0.0
    cash_entry = None
    trade_entries = []  # for trade log

    # For rotation/band: start in correct position on first day
    if (is_rotation or is_band) and not aligned.empty:
        first_fg = aligned.iloc[0]["FG"]
        first_price = aligned.iloc[0]["Price"]
        first_cprice = aligned.iloc[0].get("CashPrice", None)

        if is_band:
            in_band = buy_level <= first_fg <= sell_level
        else:
            in_band = first_fg >= buy_level

        if in_band:
            shares = current_equity / first_price
            entry_price = first_price
            entry_date = aligned.index[0]
            in_position = True
        elif first_cprice is not None and first_cprice > 0:
            cash_shares = current_equity / first_cprice

    # For confirmed momentum: track if F&G was below buy_level before crossing above
    was_below_buy = True  # assume starts below

    for date, row in aligned.iterrows():
        fg = row["FG"]
        price = row["Price"]
        c_price = row.get("CashPrice", None)

        # Determine entry/exit signals based on strategy
        should_enter = False
        should_exit = False

        if is_rotation:
            new_risk_on = fg >= buy_level
            if not in_position and new_risk_on:
                should_enter = True
            elif in_position and not new_risk_on:
                should_exit = True
        elif is_band:
            in_the_band = buy_level <= fg <= sell_level
            if not in_position and in_the_band:
                should_enter = True
            elif in_position and not in_the_band:
                should_exit = True
        elif not in_position:
            if is_confirmed:
                # Confirmed momentum: must have been below buy_level first, then cross above
                if fg < buy_level:
                    was_below_buy = True
                elif fg >= buy_level and was_below_buy:
                    should_enter = True
                    was_below_buy = False
            elif is_momentum:
                should_enter = fg >= buy_level
            else:  # contrarian, wait
                should_enter = fg <= buy_level
        else:
            hold_counter += 1
            if is_wait:
                should_exit = hold_counter >= hold_days
            elif is_momentum or is_confirmed:
                should_exit = fg < sell_level
            else:  # contrarian
                should_exit = fg >= sell_level

        # Execute trades
        if should_enter and not in_position:
            # Exit cash position if any
            if cash_shares > 0 and c_price is not None and c_price > 0:
                current_equity = cash_shares * c_price
                cash_shares = 0.0

            shares = current_equity / price
            entry_price = price
            entry_date = date
            in_position = True
            hold_counter = 0

        elif should_exit and in_position:
            current_equity = shares * price
            ret = (price / entry_price - 1) * 100 if entry_price else 0
            trade_entries.append((entry_date, date, entry_price, price, ret,
                                 (date - entry_date).days))
            shares = 0.0
            in_position = False

            # Enter cash position
            if cash_ticker and c_price is not None and c_price > 0:
                cash_shares = current_equity / c_price
                cash_entry = c_price

        # Track daily equity
        if in_position:
            daily_eq = shares * price
        elif cash_shares > 0 and c_price is not None and c_price > 0:
            daily_eq = cash_shares * c_price
        else:
            daily_eq = current_equity

        equity_values.append({"Date": date, "Equity": daily_eq})

    # Build results
    eq_df = pd.DataFrame(equity_values)
    if eq_df.empty:
        st.info("No data to display.")
        return

    trades_df = pd.DataFrame(trade_entries,
                              columns=["Entry", "Exit", "EntryPrice", "ExitPrice", "Return", "Days"])

    # Buy & hold equity
    bh_prices = aligned["Price"]
    bh_equity = (bh_prices / bh_prices.iloc[0]) * 10000
    bh_df = pd.DataFrame({"Date": bh_equity.index, "BuyHold": bh_equity.values})

    # Stats
    final_equity = eq_df["Equity"].iloc[-1]
    total_return = (final_equity / 10000 - 1) * 100
    bh_return = (bh_equity.iloc[-1] / 10000 - 1) * 100

    # Max drawdown
    eq_series = eq_df.set_index("Date")["Equity"]
    running_max = eq_series.cummax()
    drawdown = (eq_series - running_max) / running_max * 100
    max_dd = drawdown.min()

    # Buy & hold max drawdown
    bh_running_max = bh_equity.cummax()
    bh_dd = (bh_equity - bh_running_max) / bh_running_max * 100
    bh_max_dd = bh_dd.min()

    total_trades = len(trades_df)
    win_trades = (trades_df["Return"] > 0).sum() if total_trades > 0 else 0
    win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0
    avg_return = trades_df["Return"].mean() if total_trades > 0 else 0
    avg_days = trades_df["Days"].mean() if total_trades > 0 else 0

    # % time in market (risk-on)
    days_in_market = trades_df["Days"].sum() if total_trades > 0 else 0
    total_days = len(aligned)
    pct_in_market = round(days_in_market / total_days * 100, 1) if total_days > 0 else 0

    # KPI strip
    k1, k2, k3, k4, k5, k6, k7, k8 = st.columns(8)
    with k1:
        c = colors["green"] if total_return > 0 else colors["red"]
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Strategy</div>'
            f'<div style="font-size:18px; font-weight:700; color:{c};">{total_return:+.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k2:
        c = colors["green"] if bh_return > 0 else colors["red"]
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Buy&amp;Hold {etf}</div>'
            f'<div style="font-size:18px; font-weight:700; color:{c};">{bh_return:+.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k3:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Max Drawdown</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["red"]};">{max_dd:.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k4:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">B&amp;H Max DD</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text_muted"]};">{bh_max_dd:.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k5:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Trades</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text"]};">{total_trades}</div>'
            f'</div>', unsafe_allow_html=True)
    with k6:
        wc = colors["green"] if win_rate > 50 else colors["red"]
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Win Rate</div>'
            f'<div style="font-size:18px; font-weight:700; color:{wc};">{win_rate:.0f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k7:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Avg Days</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text"]};">{avg_days:.0f}</div>'
            f'</div>', unsafe_allow_html=True)
    with k8:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">In Market</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text"]};">{pct_in_market:.0f}%</div>'
            f'</div>', unsafe_allow_html=True)

    # Equity curve chart with F&G overlay and risk-on/off bands
    eq_line = (
        alt.Chart(eq_df)
        .mark_line(strokeWidth=2, color="#3D85C6")
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
            y=alt.Y("Equity:Q", title="Portfolio Value ($)"),
            tooltip=[alt.Tooltip("Equity:Q", format="$,.0f"), "Date:T"],
        )
    )

    bh_line = (
        alt.Chart(bh_df)
        .mark_line(strokeWidth=1, opacity=0.5, color=colors["text_muted"])
        .encode(
            x="Date:T",
            y="BuyHold:Q",
            tooltip=[alt.Tooltip("BuyHold:Q", format="$,.0f"), "Date:T"],
        )
    )

    # F&G overlay on right axis — super faint, with buy/sell level lines
    fg_overlay_df = aligned[["FG"]].reset_index()
    fg_overlay_df.columns = ["Date", "FG"]
    _fg_scale = alt.Scale(domain=[0, 100])

    fg_line = (
        alt.Chart(fg_overlay_df)
        .mark_line(strokeWidth=0.8, opacity=0.2, color="#E8A838")
        .encode(
            x="Date:T",
            y=alt.Y("FG:Q", title="F&G", scale=_fg_scale,
                     axis=alt.Axis(orient="right")),
        )
    )

    # Buy/sell level reference lines on F&G axis
    d_min_fg, d_max_fg = fg_overlay_df["Date"].min(), fg_overlay_df["Date"].max()
    buy_ref = pd.DataFrame([{"Date": d_min_fg, "FG": float(buy_level)},
                             {"Date": d_max_fg, "FG": float(buy_level)}])
    buy_ref_line = (
        alt.Chart(buy_ref)
        .mark_line(strokeDash=[4, 4], strokeWidth=0.7, opacity=0.4, color=colors["red"])
        .encode(x="Date:T", y=alt.Y("FG:Q", scale=_fg_scale))
    )

    if sell_level < 100 and sell_level != buy_level:
        sell_ref = pd.DataFrame([{"Date": d_min_fg, "FG": float(sell_level)},
                                  {"Date": d_max_fg, "FG": float(sell_level)}])
        sell_ref_line = (
            alt.Chart(sell_ref)
            .mark_line(strokeDash=[4, 4], strokeWidth=0.7, opacity=0.4, color=colors["green"])
            .encode(x="Date:T", y=alt.Y("FG:Q", scale=_fg_scale))
        )
    else:
        sell_ref_line = alt.Chart(pd.DataFrame()).mark_point()

    equity_layers = bh_line + eq_line
    fg_layers = fg_line + buy_ref_line + sell_ref_line
    chart = alt.layer(equity_layers, fg_layers).resolve_scale(y="independent")

    st.altair_chart(
        _style_chart(chart, colors, 300),
        use_container_width=True,
    )

    try:
        def_label = defensive_etf if (is_rotation or is_band) else cash_etf
    except NameError:
        def_label = cash_etf
    cash_note = f" When out of market: {def_label}." if "Cash" not in str(def_label) else ""
    st.caption(
        f"Blue = strategy equity, Grey = buy & hold {etf}. Starting capital $10,000.{cash_note} "
        f"Faint orange = F&G index (right axis). Red/green dashed = buy/sell levels. "
        f"Backtests do not account for transaction costs, slippage, or taxes."
    )

    # Drawdown chart
    dd_df = pd.DataFrame({"Date": eq_series.index, "Strategy": drawdown.values})
    bh_dd_series = (bh_equity - bh_equity.cummax()) / bh_equity.cummax() * 100
    bh_dd_df = pd.DataFrame({"Date": bh_dd_series.index, "BuyHold": bh_dd_series.values})

    strat_dd_line = (
        alt.Chart(dd_df)
        .mark_area(opacity=0.4, color="#3D85C6",
                   line={"color": "#3D85C6", "strokeWidth": 1})
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
            y=alt.Y("Strategy:Q", title="Drawdown (%)"),
            tooltip=[alt.Tooltip("Strategy:Q", format=".1f"), "Date:T"],
        )
    )

    bh_dd_line = (
        alt.Chart(bh_dd_df)
        .mark_line(strokeWidth=1, opacity=0.4, color=colors["text_muted"])
        .encode(
            x="Date:T",
            y="BuyHold:Q",
            tooltip=[alt.Tooltip("BuyHold:Q", format=".1f"), "Date:T"],
        )
    )

    st.altair_chart(
        _style_chart(bh_dd_line + strat_dd_line, colors, 150),
        use_container_width=True,
    )
    st.caption(f"Blue area = strategy drawdown, Grey = {etf} buy & hold drawdown.")

    # Trade log
    if total_trades > 0:
        with st.expander(f"Trade Log ({total_trades} trades)", expanded=False):
            log_df = trades_df.copy()
            log_df["Entry"] = log_df["Entry"].dt.strftime("%Y-%m-%d")
            log_df["Exit"] = log_df["Exit"].dt.strftime("%Y-%m-%d")
            log_df["EntryPrice"] = log_df["EntryPrice"].round(2)
            log_df["ExitPrice"] = log_df["ExitPrice"].round(2)
            log_df["Return"] = log_df["Return"].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(log_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Tab 2: Market Breadth
# ---------------------------------------------------------------------------

def _render_breadth_tab(colors: dict, theme: str):
    """S&P 500 market breadth analysis."""

    with st.spinner("Computing breadth for S&P 500 constituents..."):
        breadth = fetch_breadth_data()
    if not breadth:
        st.warning("Unable to compute breadth data. Try again later.")
        return

    pct_20 = breadth.get("pct_above_20", 0)
    pct_50 = breadth["pct_above_50"]
    pct_200 = breadth["pct_above_200"]
    total = breadth["total_stocks"]

    # KPI strip
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    def _breadth_color(pct):
        if pct >= 70:
            return colors["green"]
        elif pct >= 40:
            return colors["text"]
        else:
            return colors["red"]

    with kpi1:
        c = _breadth_color(pct_20)
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:12px;">'
            f'<div style="font-size:11px; color:{colors["text_muted"]}; text-transform:uppercase;">% Above 20-Day MA</div>'
            f'<div style="font-size:28px; font-weight:700; color:{c};">{pct_20:.0f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with kpi2:
        c = _breadth_color(pct_50)
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:12px;">'
            f'<div style="font-size:11px; color:{colors["text_muted"]}; text-transform:uppercase;">% Above 50-Day MA</div>'
            f'<div style="font-size:28px; font-weight:700; color:{c};">{pct_50:.0f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with kpi3:
        c = _breadth_color(pct_200)
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:12px;">'
            f'<div style="font-size:11px; color:{colors["text_muted"]}; text-transform:uppercase;">% Above 200-Day MA</div>'
            f'<div style="font-size:28px; font-weight:700; color:{c};">{pct_200:.0f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with kpi4:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:12px;">'
            f'<div style="font-size:11px; color:{colors["text_muted"]}; text-transform:uppercase;">Universe</div>'
            f'<div style="font-size:28px; font-weight:700; color:{colors["text"]};">{total}</div>'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">S&P 500 constituents</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Fetch SPY for overlay
    spy_df = _fetch_spy_overlay("2024-01-01")
    _breadth_scale = alt.Scale(domain=[0, 100])

    # Helper to build breadth chart with SPY overlay
    def _breadth_chart(hist_data, title, chart_color, y_title):
        if hist_data.empty:
            return

        st.markdown(
            f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 4px 0;">'
            f'{title}</div>',
            unsafe_allow_html=True,
        )

        # Add ref lines as extra rows in the data so they share the same y-field "Pct"
        d_min, d_max = hist_data["Date"].min(), hist_data["Date"].max()
        ref_80 = pd.DataFrame([{"Date": d_min, "Pct": 80}, {"Date": d_max, "Pct": 80}])
        ref_20 = pd.DataFrame([{"Date": d_min, "Pct": 20}, {"Date": d_max, "Pct": 20}])

        area = (
            alt.Chart(hist_data)
            .mark_area(opacity=0.3, color=chart_color,
                       line={"color": chart_color, "strokeWidth": 1.5})
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y-%m")),
                y=alt.Y("Pct:Q", title=y_title, scale=_breadth_scale),
                tooltip=[alt.Tooltip("Pct:Q", format=".1f"), "Date:T"],
            )
        )

        ob = (
            alt.Chart(ref_80).mark_line(strokeDash=[6, 3], strokeWidth=1, color=colors["green"])
            .encode(x="Date:T", y=alt.Y("Pct:Q", scale=_breadth_scale))
        )
        os_ = (
            alt.Chart(ref_20).mark_line(strokeDash=[6, 3], strokeWidth=1, color=colors["red"])
            .encode(x="Date:T", y=alt.Y("Pct:Q", scale=_breadth_scale))
        )

        if spy_df is not None:
            d_min_ts = hist_data["Date"].min()
            d_max_ts = hist_data["Date"].max()
            spy_clipped = spy_df[(spy_df["Date"] >= d_min_ts) & (spy_df["Date"] <= d_max_ts)]

            if not spy_clipped.empty:
                spy_line = (
                    alt.Chart(spy_clipped)
                    .mark_line(strokeWidth=1, opacity=0.35, color=colors["green"])
                    .encode(
                        x="Date:T",
                        y=alt.Y("SPY:Q", title="SPY",
                                scale=alt.Scale(zero=False),
                                axis=alt.Axis(orient="right")),
                        tooltip=[alt.Tooltip("SPY:Q", format=",.0f"), "Date:T"],
                    )
                )
                # Use explicit alt.layer with separate groups for proper dual-axis
                chart = alt.layer(area, ob, os_, spy_line).resolve_scale(y="independent")
            else:
                chart = os_ + ob + area
        else:
            chart = os_ + ob + area

        st.altair_chart(_style_chart(chart, colors, 280), width="stretch")

    # Render all three charts
    _breadth_chart(
        breadth.get("history_200", pd.DataFrame()),
        f"% of S&P 500 Above 200-Day Moving Average ({total} stocks)",
        "#3D85C6", "% Above 200-Day MA",
    )
    _breadth_chart(
        breadth.get("history_50", pd.DataFrame()),
        f"% of S&P 500 Above 50-Day Moving Average",
        "#E8A838", "% Above 50-Day MA",
    )
    _breadth_chart(
        breadth.get("history_20", pd.DataFrame()),
        f"% of S&P 500 Above 20-Day Moving Average",
        "#8B5CF6", "% Above 20-Day MA",
    )

    st.caption(
        "Market breadth measures the participation of stocks in a market move. "
        "When fewer than 20% of stocks are above their 200-day MA, the market is broadly oversold — "
        "a historically contrarian buy signal. Above 80% suggests overbought conditions. "
        "The 20-day MA is the most responsive — sharp drops signal short-term fear. "
        f"S&P 500 constituent list sourced from Wikipedia ({total} stocks)."
    )


# ---------------------------------------------------------------------------
# Tab 3: AAII Survey
# ---------------------------------------------------------------------------

def _render_aaii_tab(colors: dict, theme: str):
    """AAII Investor Sentiment Survey."""

    df = fetch_aaii_sentiment()

    # Show data freshness + update button
    if not df.empty:
        freshness_col, update_col = st.columns([8, 2])
        latest_date = df["Date"].max().strftime("%Y-%m-%d")
        with freshness_col:
            st.caption(
                f"Data through **{latest_date}** · Weekly survey from "
                f"[AAII](https://www.aaii.com/sentimentsurvey) (1987–present)"
            )
        with update_col:
            if st.button("🔄 Update AAII", key="refresh_aaii", help="Download latest from AAII website"):
                with st.spinner("Downloading from AAII..."):
                    if download_aaii_xls():
                        fetch_aaii_sentiment.clear()
                        st.rerun()
                    else:
                        st.error("Download failed. AAII may be blocking requests.")

    if df.empty:
        st.info("AAII sentiment data not available.")
        if st.button("📥 Download AAII Data", key="download_aaii", type="primary"):
            with st.spinner("Downloading from AAII website..."):
                if download_aaii_xls():
                    fetch_aaii_sentiment.clear()
                    st.rerun()
                else:
                    st.error("Download failed. Try again later.")

        # Show educational content anyway
        st.markdown(
            f"""
            <div class="factor-card" style="padding:16px;">
                <div style="font-size:15px; font-weight:600; color:{colors['text_header']}; margin-bottom:8px;">
                    About the AAII Sentiment Survey
                </div>
                <div style="font-size:13px; color:{colors['text']}; line-height:1.7;">
                    <p>The American Association of Individual Investors (AAII) has conducted a weekly
                    sentiment survey since 1987, asking members whether they are bullish, bearish,
                    or neutral on the stock market over the next six months.</p>
                    <p><b>Historical averages:</b> Bullish ~37.5%, Bearish ~31%, Neutral ~31.5%</p>
                    <p><b>Contrarian signal:</b> When the Bull-Bear spread drops below -20,
                    it has historically preceded positive 6-month returns. Extreme bearish readings
                    are often seen near market bottoms.</p>
                    <p><b>Data source:</b> <a href="https://www.aaii.com/sentimentsurvey" target="_blank"
                    style="color:#3D85C6;">AAII Sentiment Survey</a></p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # If we have data, render it
    latest = df.iloc[-1]
    bull = latest["Bullish"]
    bear = latest["Bearish"]
    neutral = latest.get("Neutral", 100 - bull - bear)
    spread = latest.get("Spread", bull - bear)

    # KPI strip
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:10px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]}; text-transform:uppercase;">Bullish</div>'
            f'<div style="font-size:28px; font-weight:700; color:{colors["green"]};">{bull:.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with kpi2:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:10px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]}; text-transform:uppercase;">Neutral</div>'
            f'<div style="font-size:28px; font-weight:700; color:{colors["text_muted"]};">{neutral:.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with kpi3:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:10px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]}; text-transform:uppercase;">Bearish</div>'
            f'<div style="font-size:28px; font-weight:700; color:{colors["red"]};">{bear:.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with kpi4:
        sp_color = colors["green"] if spread > 0 else colors["red"]
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:10px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]}; text-transform:uppercase;">Bull-Bear Spread</div>'
            f'<div style="font-size:28px; font-weight:700; color:{sp_color};">{spread:+.1f}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Date range selector
    range_opts = ["2 Years", "5 Years", "10 Years", "All"]
    range_sel = st.selectbox("Chart range", range_opts, index=1, key="aaii_range")
    range_days = {"2 Years": 730, "5 Years": 1825, "10 Years": 3650, "All": 0}
    if range_sel == "All":
        cutoff = df["Date"].min()
    else:
        cutoff = df["Date"].max() - pd.Timedelta(days=range_days[range_sel])
    recent = df[df["Date"] >= cutoff].copy()

    if not recent.empty:
        # Stacked area chart with muted colors
        melted = recent.melt(id_vars="Date", value_vars=["Bullish", "Neutral", "Bearish"],
                             var_name="Sentiment", value_name="Pct")

        area = (
            alt.Chart(melted)
            .mark_area(opacity=0.7)
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                y=alt.Y("Pct:Q", title="Percentage", stack="normalize"),
                color=alt.Color(
                    "Sentiment:N",
                    scale=alt.Scale(
                        domain=["Bullish", "Neutral", "Bearish"],
                        range=["#5B9F5B", "#7A8A9A", "#B85C5C"],
                    ),
                    legend=alt.Legend(orient="top", title=None),
                ),
                tooltip=["Sentiment:N", alt.Tooltip("Pct:Q", format=".1f"), "Date:T"],
                order=alt.Order("Sentiment:N", sort="descending"),
            )
        )

        # SPY overlay
        spy_df = _fetch_spy_overlay(recent["Date"].min().strftime("%Y-%m-%d"))
        if spy_df is not None:
            d_min = recent["Date"].min()
            d_max = recent["Date"].max()
            spy_clipped = spy_df[(spy_df["Date"] >= d_min) & (spy_df["Date"] <= d_max)]
            if not spy_clipped.empty:
                spy_line = (
                    alt.Chart(spy_clipped)
                    .mark_line(strokeWidth=1, opacity=0.5, color=colors["green"])
                    .encode(
                        x="Date:T",
                        y=alt.Y("SPY:Q", title="SPY", scale=alt.Scale(zero=False),
                                axis=alt.Axis(orient="right")),
                        tooltip=[alt.Tooltip("SPY:Q", format=",.0f"), "Date:T"],
                    )
                )
                chart = alt.layer(area, spy_line).resolve_scale(y="independent")
            else:
                chart = area
        else:
            chart = area

        st.altair_chart(_style_chart(chart, colors, 300), width="stretch")

    # Bull-Bear spread chart
    if not recent.empty:
        st.markdown(
            f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
            f'Bull-Bear Spread</div>',
            unsafe_allow_html=True,
        )

        spread_line = (
            alt.Chart(recent)
            .mark_area(opacity=0.3, color="#3D85C6",
                       line={"color": "#3D85C6", "strokeWidth": 1.5})
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                y=alt.Y("Spread:Q", title="Bull-Bear Spread (%)"),
                tooltip=[alt.Tooltip("Spread:Q", format=".1f"), "Date:T"],
            )
        )

        d_min_s, d_max_s = recent["Date"].min(), recent["Date"].max()
        ref_p20 = pd.DataFrame([{"Date": d_min_s, "Spread": 20}, {"Date": d_max_s, "Spread": 20}])
        ref_m20 = pd.DataFrame([{"Date": d_min_s, "Spread": -20}, {"Date": d_max_s, "Spread": -20}])
        ref_zero = pd.DataFrame([{"Date": d_min_s, "Spread": 0}, {"Date": d_max_s, "Spread": 0}])

        r_p20 = alt.Chart(ref_p20).mark_line(strokeDash=[4, 4], strokeWidth=0.8, color=colors["green"]).encode(x="Date:T", y="Spread:Q")
        r_m20 = alt.Chart(ref_m20).mark_line(strokeDash=[4, 4], strokeWidth=0.8, color=colors["red"]).encode(x="Date:T", y="Spread:Q")
        r_zero = alt.Chart(ref_zero).mark_line(strokeDash=[4, 4], strokeWidth=0.8, color=colors["text_muted"]).encode(x="Date:T", y="Spread:Q")

        st.altair_chart(
            _style_chart(r_m20 + r_zero + r_p20 + spread_line, colors, 220),
            use_container_width=True,
        )

    st.caption(
        "AAII Bull-Bear spread is a contrarian indicator. Readings below -20 have "
        "historically preceded positive 6-month returns. Above +20 often precedes corrections. "
        "Historical averages: Bullish 37.5%, Bearish 31%, Neutral 31.5%. "
        "Data from AAII Sentiment Survey (weekly since 1987)."
    )

    # ---- AAII Backtester ----
    if len(df) > 100:
        _render_aaii_backtest(df, colors, theme)


def _render_aaii_backtest(df: pd.DataFrame, colors: dict, theme: str):
    """AAII sentiment backtester — contrarian strategies based on Bull-Bear spread."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'AAII Sentiment Backtester</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Strategy Descriptions", expanded=False):
        st.markdown(
            f"""
            <div style="color:{colors['text']}; font-size:12px; line-height:1.7;">
            <p style="color:{colors['text_muted']}; font-weight:600; text-transform:uppercase; font-size:11px; margin-top:8px;">Contrarian Strategies (buy fear)</p>

            <p><b>Contrarian Spread</b> — Buy when Bull-Bear spread drops below level (extreme bearishness),
            sell when rises above. Classic contrarian.
            <i>Example: Buy below -20, sell above +10. Spread hits -25 → BUY. Rises to +15 → SELL.</i></p>

            <p><b>Buy extreme fear &amp; wait N weeks</b> — Buy when spread drops below threshold,
            hold for N weeks regardless. Tests the optimal "buy the panic" horizon.
            <i>Example: Buy below -20, hold 12 weeks.</i></p>

            <p style="color:{colors['text_muted']}; font-weight:600; text-transform:uppercase; font-size:11px; margin-top:12px;">Trend-Following Strategies (buy strength)</p>

            <p><b>Ride the Bulls</b> — Buy when Bullish % rises above threshold (strong optimism),
            sell when it drops below. Follows the crowd when conviction is high.
            <i>Example: Buy above 45%, sell below 30%. Bullish hits 50% → BUY. Drops to 28% → SELL.</i></p>

            <p><b>Positive Spread Momentum</b> — Buy when spread rises above a positive level
            (bulls dominate bears), sell when it drops below. Rides the bullish wave.
            <i>Example: Buy above +10, sell below -5. Spread hits +15 → BUY. Drops to -8 → SELL.</i></p>

            <p><b>Low Bears = Green Light</b> — Buy when Bearish % drops below threshold
            (few people are worried), sell when it rises above. Invests when fear is absent.
            <i>Example: Buy below 25%, sell above 40%. Bearish drops to 20% → BUY. Rises to 42% → SELL.</i></p>

            <p style="color:{colors['text_muted']}; font-weight:600; text-transform:uppercase; font-size:11px; margin-top:12px;">Hybrid Strategies</p>

            <p><b>Neutral Zone Exit</b> — Buy when Bullish % exceeds Bearish % by a margin (spread &gt; threshold),
            sell only when Bearish % exceeds Bullish % by a margin (spread &lt; -threshold). Stays invested
            during the entire "positive outlook" zone. A simple trend filter.
            <i>Example: Buy when spread &gt; +5, sell when spread &lt; -5. Invested as long as bulls lead bears.</i></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _AAII_STRATEGIES = [
        "── Contrarian (buy fear) ──",
        "Contrarian Spread",
        "Buy extreme fear & wait N weeks",
        "── Trend-Following (buy strength) ──",
        "Ride the Bulls (high bullish %)",
        "Positive Spread Momentum",
        "Low Bears = Green Light",
        "── Hybrid ──",
        "Neutral Zone Exit",
    ]

    col1, col2 = st.columns(2)
    with col1:
        strategy = st.selectbox("Strategy", _AAII_STRATEGIES, key="aaii_bt_strat",
                                format_func=lambda x: x if not x.startswith("──") else x)
    with col2:
        etf = st.selectbox("ETF to trade", ["SPY", "QQQ", "IWM", "TLT", "GLD", "SH"], key="aaii_bt_etf")

    # Skip separator entries
    if strategy.startswith("──"):
        st.info("Please select a strategy from the dropdown.")
        return

    col3, col4, col5 = st.columns(3)
    is_contrarian = "contrarian spread" in strategy.lower()
    is_wait_wk = "wait" in strategy.lower()
    is_ride_bulls = "ride the bulls" in strategy.lower()
    is_pos_spread = "positive spread" in strategy.lower()
    is_low_bears = "low bears" in strategy.lower()
    is_neutral_zone = "neutral zone" in strategy.lower()

    with col3:
        if is_contrarian or is_wait_wk:
            buy_val = st.slider("Buy when spread below", -50, 20, -20, 5, key="aaii_bt_buy",
                                help="Enter when Bull-Bear spread drops below this")
        elif is_ride_bulls:
            buy_val = st.slider("Buy when Bullish % above", 20, 70, 45, 5, key="aaii_bt_buy",
                                help="Enter when Bullish % rises above this")
        elif is_pos_spread:
            buy_val = st.slider("Buy when spread above", -10, 30, 10, 5, key="aaii_bt_buy",
                                help="Enter when Bull-Bear spread rises above this")
        elif is_low_bears:
            buy_val = st.slider("Buy when Bearish % below", 15, 45, 25, 5, key="aaii_bt_buy",
                                help="Enter when Bearish % drops below this")
        elif is_neutral_zone:
            buy_val = st.slider("Buy when spread above", -10, 20, 5, 5, key="aaii_bt_buy",
                                help="Enter when bulls lead bears by this margin")
        else:
            buy_val = st.slider("Buy level", -50, 50, 0, 5, key="aaii_bt_buy")

    with col4:
        if is_wait_wk:
            hold_weeks = st.slider("Hold weeks", 4, 52, 12, 4, key="aaii_bt_hold")
            sell_val = 999
        elif is_contrarian:
            sell_val = st.slider("Sell when spread above", -10, 40, 10, 5, key="aaii_bt_sell")
            hold_weeks = 0
        elif is_ride_bulls:
            sell_val = st.slider("Sell when Bullish % below", 15, 50, 30, 5, key="aaii_bt_sell",
                                 help="Exit when Bullish % drops below this")
            hold_weeks = 0
        elif is_pos_spread:
            sell_val = st.slider("Sell when spread below", -30, 10, -5, 5, key="aaii_bt_sell",
                                 help="Exit when spread drops below this")
            hold_weeks = 0
        elif is_low_bears:
            sell_val = st.slider("Sell when Bearish % above", 25, 60, 40, 5, key="aaii_bt_sell",
                                 help="Exit when Bearish % rises above this")
            hold_weeks = 0
        elif is_neutral_zone:
            sell_val = st.slider("Sell when spread below", -30, 5, -5, 5, key="aaii_bt_sell",
                                 help="Exit when bears lead bulls by this margin")
            hold_weeks = 0
        else:
            sell_val = st.slider("Sell level", -50, 50, 0, 5, key="aaii_bt_sell")
            hold_weeks = 0

    with col5:
        cash_etf = st.selectbox("When out of market:",
                                ["Cash (0%)", "TLT (bonds)", "GLD (gold)", "SH (short SPY)"],
                                key="aaii_bt_cash")

    # Fetch ETF — AAII is weekly, so use weekly prices
    d_min = df["Date"].min().strftime("%Y-%m-%d")
    etf_prices = _fetch_etf_for_backtest(etf, d_min)
    if etf_prices.empty:
        st.warning(f"Unable to fetch {etf} data.")
        return

    cash_ticker = None
    cash_prices = pd.Series(dtype=float)
    if "TLT" in cash_etf:
        cash_ticker = "TLT"
    elif "GLD" in cash_etf:
        cash_ticker = "GLD"
    elif "SH" in cash_etf:
        cash_ticker = "SH"
    if cash_ticker and cash_ticker != etf:
        cash_prices = _fetch_etf_for_backtest(cash_ticker, d_min)

    # Align AAII weekly data with daily ETF prices (forward-fill AAII to daily)
    aaii_daily = df.set_index("Date")[["Bullish", "Bearish", "Spread"]].reindex(
        etf_prices.index, method="ffill"
    )
    aligned = pd.DataFrame({
        "Bullish": aaii_daily["Bullish"],
        "Bearish": aaii_daily["Bearish"],
        "Spread": aaii_daily["Spread"],
        "Price": etf_prices,
    })
    if not cash_prices.empty:
        aligned["CashPrice"] = cash_prices
    aligned = aligned.dropna(subset=["Spread", "Price"])

    if len(aligned) < 100:
        st.warning("Not enough data for backtest.")
        return

    # Run backtest
    equity_values = []
    current_equity = 10000.0
    in_position = False
    entry_price = None
    shares = 0.0
    hold_counter = 0
    cash_shares = 0.0
    trade_entries = []

    for date, row in aligned.iterrows():
        price = row["Price"]
        c_price = row.get("CashPrice", None)
        spread_v = row["Spread"]
        bull_v = row["Bullish"]
        bear_v = row["Bearish"]

        should_enter = False
        should_exit = False

        if not in_position:
            if is_contrarian or is_wait_wk:
                should_enter = spread_v <= buy_val          # buy on extreme bearishness
            elif is_ride_bulls:
                should_enter = bull_v >= buy_val             # buy on high bullish %
            elif is_pos_spread:
                should_enter = spread_v >= buy_val           # buy on positive spread
            elif is_low_bears:
                should_enter = bear_v <= buy_val             # buy when few are bearish
            elif is_neutral_zone:
                should_enter = spread_v >= buy_val           # buy when bulls lead
        else:
            hold_counter += 1
            if is_wait_wk:
                should_exit = hold_counter >= hold_weeks * 5
            elif is_contrarian:
                should_exit = spread_v >= sell_val           # sell when spread recovers
            elif is_ride_bulls:
                should_exit = bull_v <= sell_val             # sell when bullish % drops
            elif is_pos_spread:
                should_exit = spread_v <= sell_val           # sell when spread turns negative
            elif is_low_bears:
                should_exit = bear_v >= sell_val             # sell when bears increase
            elif is_neutral_zone:
                should_exit = spread_v <= sell_val           # sell when bears take over

        if should_enter and not in_position:
            if cash_shares > 0 and c_price and c_price > 0:
                current_equity = cash_shares * c_price
                cash_shares = 0
            shares = current_equity / price
            entry_price = price
            entry_date = date
            in_position = True
            hold_counter = 0
        elif should_exit and in_position:
            current_equity = shares * price
            ret = (price / entry_price - 1) * 100 if entry_price else 0
            trade_entries.append((entry_date, date, entry_price, price, ret, (date - entry_date).days))
            shares = 0
            in_position = False
            if cash_ticker and c_price and c_price > 0:
                cash_shares = current_equity / c_price

        if in_position:
            daily_eq = shares * price
        elif cash_shares > 0 and c_price and c_price > 0:
            daily_eq = cash_shares * c_price
        else:
            daily_eq = current_equity
        equity_values.append({"Date": date, "Equity": daily_eq})

    eq_df = pd.DataFrame(equity_values)
    trades_df = pd.DataFrame(trade_entries,
                              columns=["Entry", "Exit", "EntryPrice", "ExitPrice", "Return", "Days"])

    if eq_df.empty:
        st.info("No data to display.")
        return

    # Stats
    final_eq = eq_df["Equity"].iloc[-1]
    total_return = (final_eq / 10000 - 1) * 100
    bh_equity = (aligned["Price"] / aligned["Price"].iloc[0]) * 10000
    bh_return = (bh_equity.iloc[-1] / 10000 - 1) * 100

    eq_series = eq_df.set_index("Date")["Equity"]
    max_dd = ((eq_series - eq_series.cummax()) / eq_series.cummax() * 100).min()
    bh_max_dd = ((bh_equity - bh_equity.cummax()) / bh_equity.cummax() * 100).min()

    total_trades = len(trades_df)
    win_rate = (trades_df["Return"] > 0).sum() / total_trades * 100 if total_trades > 0 else 0
    days_in = trades_df["Days"].sum() if total_trades > 0 else 0
    pct_in = round(days_in / len(aligned) * 100, 1) if len(aligned) > 0 else 0

    # KPIs
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    for col, label, val, fmt, clr in [
        (k1, "Strategy", total_return, "+.1f", colors["green"] if total_return > 0 else colors["red"]),
        (k2, f"B&H {etf}", bh_return, "+.1f", colors["green"] if bh_return > 0 else colors["red"]),
        (k3, "Max DD", max_dd, ".1f", colors["red"]),
        (k4, "Trades", total_trades, "d", colors["text"]),
        (k5, "Win Rate", win_rate, ".0f", colors["green"] if win_rate > 50 else colors["red"]),
        (k6, "In Market", pct_in, ".0f", colors["text"]),
    ]:
        sfx = "%" if label not in ("Trades",) else ""
        with col:
            st.markdown(
                f'<div class="factor-card" style="text-align:center; padding:8px;">'
                f'<div style="font-size:10px; color:{colors["text_muted"]};">{label}</div>'
                f'<div style="font-size:18px; font-weight:700; color:{clr};">{val:{fmt}}{sfx}</div>'
                f'</div>', unsafe_allow_html=True)

    # Equity chart
    bh_df = pd.DataFrame({"Date": bh_equity.index, "BuyHold": bh_equity.values})
    eq_line = alt.Chart(eq_df).mark_line(strokeWidth=2, color="#3D85C6").encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
        y=alt.Y("Equity:Q", title="Portfolio ($)"),
        tooltip=[alt.Tooltip("Equity:Q", format="$,.0f"), "Date:T"],
    )
    bh_line = alt.Chart(bh_df).mark_line(strokeWidth=1, opacity=0.5, color=colors["text_muted"]).encode(
        x="Date:T", y="BuyHold:Q",
        tooltip=[alt.Tooltip("BuyHold:Q", format="$,.0f"), "Date:T"],
    )
    st.altair_chart(_style_chart(bh_line + eq_line, colors, 280), width="stretch")

    # Drawdown
    dd_vals = (eq_series - eq_series.cummax()) / eq_series.cummax() * 100
    dd_df = pd.DataFrame({"Date": dd_vals.index, "Strategy": dd_vals.values})
    bh_dd = (bh_equity - bh_equity.cummax()) / bh_equity.cummax() * 100
    bh_dd_df = pd.DataFrame({"Date": bh_dd.index, "BuyHold": bh_dd.values})

    dd_area = alt.Chart(dd_df).mark_area(opacity=0.4, color="#3D85C6",
        line={"color": "#3D85C6", "strokeWidth": 1}).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
        y=alt.Y("Strategy:Q", title="Drawdown (%)"),
        tooltip=[alt.Tooltip("Strategy:Q", format=".1f"), "Date:T"],
    )
    bh_dd_line = alt.Chart(bh_dd_df).mark_line(strokeWidth=1, opacity=0.4, color=colors["text_muted"]).encode(
        x="Date:T", y="BuyHold:Q")

    st.altair_chart(_style_chart(bh_dd_line + dd_area, colors, 150), width="stretch")
    st.caption(f"Blue = strategy, Grey = buy & hold {etf}. Backtests ignore costs/slippage.")

    if total_trades > 0:
        with st.expander(f"Trade Log ({total_trades} trades)", expanded=False):
            log = trades_df.copy()
            log["Entry"] = log["Entry"].dt.strftime("%Y-%m-%d")
            log["Exit"] = log["Exit"].dt.strftime("%Y-%m-%d")
            log["EntryPrice"] = log["EntryPrice"].round(2)
            log["ExitPrice"] = log["ExitPrice"].round(2)
            log["Return"] = log["Return"].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(log, use_container_width=True, hide_index=True)
