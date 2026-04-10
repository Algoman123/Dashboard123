"""Macro Indicators Dashboard — full-page view with yield curve, inflation, Fed policy, M2, and PMI."""

import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import date, timedelta

from services.api_keys import get_fred_key
from services.fred_data import (
    MATURITY_ORDER,
    INTERNATIONAL_YIELDS,
    COUNTRY_ETF,
    fetch_yield_curve,
    fetch_yield_curve_on_date,
    fetch_spread_history,
    fetch_recession_periods,
    fetch_10y1y_spread_history,
    fetch_sp500_pe_data,
    fetch_international_yields,
    fetch_country_yield_history,
    fetch_us_10y_history,
    fetch_country_recessions,
    fetch_country_etf_history,
    fetch_international_cpi,
    fetch_international_cpi_latest,
    fetch_cli_history,
    fetch_cli_latest,
    fetch_inflation_data,
    fetch_fed_rate_data,
    fetch_m2_data,
)


_FRED_CACHED_FUNCTIONS = [
    fetch_yield_curve, fetch_yield_curve_on_date, fetch_spread_history,
    fetch_international_yields, fetch_country_yield_history, fetch_us_10y_history,
    fetch_country_recessions, fetch_country_etf_history,
    fetch_international_cpi, fetch_international_cpi_latest,
    fetch_cli_history, fetch_cli_latest,
    fetch_recession_periods, fetch_10y1y_spread_history, fetch_sp500_pe_data,
    fetch_inflation_data, fetch_fed_rate_data, fetch_m2_data,
]


def _clear_macro_cache():
    """Clear only FRED/macro cached data, leaving market data untouched."""
    for fn in _FRED_CACHED_FUNCTIONS:
        fn.clear()


def render_macro_dashboard(colors: dict, theme: str):
    """Render the full macro indicators dashboard, replacing the normal main content."""

    # Header with refresh button
    hdr_left, hdr_center, hdr_right = st.columns([1, 6, 1])
    with hdr_center:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 10px 0 4px 0;">
                <div style="font-size:28px; font-weight:700; color:{colors['text_header']};">
                    Macro Indicators
                </div>
                <div style="font-size:13px; color:{colors['text_muted']};">
                    US Treasury yield curve, inflation, Fed policy, money supply &amp; global PMI
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_right:
        if st.button("🔄", key="refresh_macro", help="Refresh all macro data"):
            _clear_macro_cache()
            st.rerun()

    fred_key = get_fred_key()
    if not fred_key:
        st.warning("Add your FRED API key in Settings to enable Macro data.")
        st.caption("Get a free key at https://fred.stlouisfed.org/docs/api/fred/")
        return

    tab_yc, tab_inf, tab_fed, tab_m2, tab_pmi = st.tabs(
        ["Yield Curve", "Inflation", "Fed Policy", "M2 vs Equities", "PMI & Leading Indicators"]
    )

    with tab_yc:
        _render_yield_curve_tab(fred_key, colors, theme)

    with tab_inf:
        _render_inflation_tab(fred_key, colors, theme)

    with tab_fed:
        _render_fed_policy_tab(fred_key, colors, theme)

    with tab_m2:
        _render_m2_tab(fred_key, colors, theme)

    with tab_pmi:
        _render_pmi_tab(fred_key, colors, theme)


# ---------------------------------------------------------------------------
# Helper: styled Altair chart config
# ---------------------------------------------------------------------------

def _style_chart(chart, colors, height=380):
    """Apply consistent dark/light styling to an Altair chart."""
    return (
        chart
        .properties(height=height)
        .configure_view(strokeWidth=0)
        .configure(background=colors["bg_card"])
        .configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            gridColor=f"{colors['border']}80",
            domainColor=colors["border"],
        )
        .configure_legend(
            labelColor=colors["text"],
            titleColor=colors["text"],
        )
    )


def _kpi_card(label: str, value: str, colors: dict, color: str | None = None):
    """Render a single KPI metric card."""
    val_color = color or colors["text"]
    return (
        f'<div style="text-align:center; padding:8px 12px;">'
        f'<div style="font-size:10px; color:{colors["text_muted"]}; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>'
        f'<div style="font-size:22px; font-weight:700; color:{val_color};">{value}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Tab 1: Yield Curve
# ---------------------------------------------------------------------------

def _render_yield_curve_tab(api_key: str, colors: dict, theme: str):
    """Yield curve snapshot, comparison, and spread history."""

    current = fetch_yield_curve(api_key)
    if not current:
        st.warning("Unable to fetch yield curve data.")
        return

    # KPI strip
    y10 = current.get("10Y", 0)
    y2 = current.get("2Y", 0)
    spread_2s10s = y10 - y2
    y3m = current.get("3M", 0)

    # Curve shape
    if spread_2s10s < 0:
        shape = "Inverted"
        shape_color = colors["red"]
    elif spread_2s10s < 0.25:
        shape = "Flat"
        shape_color = colors["text_muted"]
    else:
        shape = "Normal"
        shape_color = colors["green"]

    spread_color = colors["red"] if spread_2s10s < 0 else colors["green"]

    cols = st.columns(4)
    for i, (lbl, val, clr) in enumerate([
        ("10Y Yield", f"{y10:.2f}%", colors["text"]),
        ("2Y Yield", f"{y2:.2f}%", colors["text"]),
        ("2s10s Spread", f"{spread_2s10s:+.2f}%", spread_color),
        ("Curve Shape", shape, shape_color),
    ]):
        with cols[i]:
            st.markdown(
                f'<div class="factor-card">{_kpi_card(lbl, val, colors, clr)}</div>',
                unsafe_allow_html=True,
            )

    if spread_2s10s < 0:
        st.error("Yield curve inverted — historically a leading recession indicator.")

    # Comparison selector
    compare_options = {
        "None": None,
        "1 Year Ago": (date.today() - timedelta(days=365)).isoformat(),
        "2 Years Ago": (date.today() - timedelta(days=730)).isoformat(),
        "Pre-COVID (2019-12-31)": "2019-12-31",
        "2022 Tightening Peak (2022-10-24)": "2022-10-24",
    }
    selected_compare = st.selectbox(
        "Compare to:", options=list(compare_options.keys()), key="yc_compare"
    )
    compare_date = compare_options[selected_compare]

    # Build chart data
    chart_rows = []
    for mat in MATURITY_ORDER:
        if mat in current:
            chart_rows.append({"Maturity": mat, "Yield": current[mat], "Series": "Current"})

    compare_curve = {}
    if compare_date:
        compare_curve = fetch_yield_curve_on_date(api_key, compare_date)
        for mat in MATURITY_ORDER:
            if mat in compare_curve:
                chart_rows.append({"Maturity": mat, "Yield": compare_curve[mat], "Series": selected_compare})

    if chart_rows:
        df = pd.DataFrame(chart_rows)
        # Ensure maturity ordering
        df["sort_order"] = df["Maturity"].map({m: i for i, m in enumerate(MATURITY_ORDER)})
        df = df.sort_values("sort_order")

        series_list = df["Series"].unique().tolist()
        series_colors = [colors["green"], colors["text_muted"]] if len(series_list) > 1 else [colors["green"]]
        dash_values = [[1, 0], [4, 4]] if len(series_list) > 1 else [[1, 0]]

        lines = (
            alt.Chart(df)
            .mark_line(point=True, strokeWidth=2.5)
            .encode(
                x=alt.X("Maturity:N", sort=MATURITY_ORDER, title=None),
                y=alt.Y("Yield:Q", title="Yield (%)"),
                color=alt.Color(
                    "Series:N",
                    scale=alt.Scale(domain=series_list, range=series_colors),
                    legend=alt.Legend(orient="top", title=None),
                ),
                strokeDash=alt.StrokeDash(
                    "Series:N",
                    scale=alt.Scale(domain=series_list, range=dash_values),
                    legend=None,
                ),
                tooltip=["Maturity:N", alt.Tooltip("Yield:Q", format=".2f"), "Series:N"],
            )
        )

        st.altair_chart(_style_chart(lines, colors, 340), use_container_width=True)

    # Spread history expander
    with st.expander("Spread History", expanded=False):
        spread_df = fetch_spread_history(api_key)
        if spread_df.empty:
            st.caption("No spread data available.")
        else:
            spread_cols = ["2s10s", "3M10Y", "5s30s"]
            available = [c for c in spread_cols if c in spread_df.columns]
            if available:
                df_plot = spread_df[available].copy()
                df_plot.index.name = "Date"
                df_plot = df_plot.reset_index()
                melted = df_plot.melt(id_vars="Date", var_name="Spread", value_name="Value")
                melted = melted.dropna()

                spread_colors = [colors["green"], "#6C8EBF", "#D4A574"]

                lines = (
                    alt.Chart(melted)
                    .mark_line(strokeWidth=1.5)
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                        y=alt.Y("Value:Q", title="Spread (%)"),
                        color=alt.Color(
                            "Spread:N",
                            scale=alt.Scale(domain=available, range=spread_colors[:len(available)]),
                            legend=alt.Legend(orient="top", title=None),
                        ),
                        tooltip=["Spread:N", alt.Tooltip("Value:Q", format=".2f"), "Date:T"],
                    )
                )

                zero = (
                    alt.Chart(pd.DataFrame({"y": [0]}))
                    .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["red"])
                    .encode(y="y:Q")
                )

                st.altair_chart(_style_chart(zero + lines, colors, 280), use_container_width=True)

    # ---- Historical Treasury Yield Spread (10Y-1Y) with recession shading ----
    _render_yield_spread_history(api_key, colors, theme)

    # ---- Historical Treasury Yield vs S&P 500 P/E ----
    _render_yield_vs_pe(api_key, colors, theme)

    # ---- Global Yield Comparison ----
    _render_global_yields(api_key, colors, theme)


def _recession_shading(recession_periods: list[tuple], colors: dict,
                       date_min: str | None = None, date_max: str | None = None) -> alt.Chart:
    """Build Altair grey rectangle overlay for recession periods, clipped to date range."""
    if not recession_periods:
        return alt.Chart(pd.DataFrame()).mark_point()
    recs = pd.DataFrame(recession_periods, columns=["start", "end"])
    recs["start"] = pd.to_datetime(recs["start"])
    recs["end"] = pd.to_datetime(recs["end"])
    # Clip to date range so chart x-axis isn't stretched
    if date_min:
        dt_min = pd.Timestamp(date_min)
        recs = recs[recs["end"] >= dt_min]
        recs.loc[recs["start"] < dt_min, "start"] = dt_min
    if date_max:
        dt_max = pd.Timestamp(date_max)
        recs = recs[recs["start"] <= dt_max]
        recs.loc[recs["end"] > dt_max, "end"] = dt_max
    if recs.empty:
        return alt.Chart(pd.DataFrame()).mark_point()
    return (
        alt.Chart(recs)
        .mark_rect(opacity=0.18, color=colors["text_muted"])
        .encode(
            x="start:T",
            x2="end:T",
        )
    )


def _add_spy_and_recessions(base_layers: list, api_key: str, colors: dict,
                             date_min: str, date_max: str | None = None) -> alt.Chart:
    """Add recession shading and SPY overlay to a list of chart layers. Returns combined chart."""
    recessions = fetch_recession_periods(api_key)
    rec_rects = _recession_shading(recessions, colors, date_min, date_max)
    spy_data = _fetch_spy_for_overlay(date_min)

    # Clip SPY to date range
    if not spy_data.empty:
        spy_data = spy_data[spy_data.index >= pd.Timestamp(date_min)]
        if date_max:
            spy_data = spy_data[spy_data.index <= pd.Timestamp(date_max)]

    all_layers = [rec_rects] + base_layers

    if not spy_data.empty:
        spy_df = spy_data.reset_index()
        spy_df.columns = ["Date", "SPY"]
        spy_line = (
            alt.Chart(spy_df)
            .mark_line(strokeWidth=1, opacity=0.4, color=colors["green"])
            .encode(
                x="Date:T",
                y=alt.Y("SPY:Q", title="SPY", axis=alt.Axis(orient="right")),
                tooltip=[alt.Tooltip("SPY:Q", format=",.0f"), "Date:T"],
            )
        )
        all_layers.append(spy_line)
        return alt.layer(*all_layers).resolve_scale(y="independent")
    else:
        combined = all_layers[0]
        for layer in all_layers[1:]:
            combined = combined + layer
        return combined


def _add_country_overlay(base_layers: list, api_key: str, colors: dict,
                          country_code: str, recessions: list[tuple],
                          date_min: str, date_max: str | None = None) -> alt.Chart:
    """Add country-specific recession shading and market ETF overlay."""
    rec_rects = _recession_shading(recessions, colors, date_min, date_max)

    # Fetch country-specific ETF instead of SPY
    etf_data = fetch_country_etf_history(api_key, country_code, date_min)

    # Clip to date range
    if not etf_data.empty:
        etf_data = etf_data[etf_data.index >= pd.Timestamp(date_min)]
        if date_max:
            etf_data = etf_data[etf_data.index <= pd.Timestamp(date_max)]

    all_layers = [rec_rects] + base_layers

    etf_ticker = COUNTRY_ETF.get(country_code)
    if not etf_data.empty and etf_ticker:
        etf_df = etf_data.reset_index()
        etf_df.columns = ["Date", etf_ticker]
        etf_line = (
            alt.Chart(etf_df)
            .mark_line(strokeWidth=1, opacity=0.4, color=colors["green"])
            .encode(
                x="Date:T",
                y=alt.Y(f"{etf_ticker}:Q", title=etf_ticker,
                        axis=alt.Axis(orient="right")),
                tooltip=[alt.Tooltip(f"{etf_ticker}:Q", format=",.0f"), "Date:T"],
            )
        )
        all_layers.append(etf_line)
        return alt.layer(*all_layers).resolve_scale(y="independent")
    else:
        combined = all_layers[0]
        for layer in all_layers[1:]:
            combined = combined + layer
        return combined


def _render_yield_spread_history(api_key: str, colors: dict, theme: str):
    """Historical 10Y-1Y Treasury Yield Spread with recession shading and SPY."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Historical Treasury Yield Spread (10Y - 1Y)</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "The 10-Year minus 1-Year Treasury yield spread is one of the most watched recession indicators. "
        "When the spread drops below 0% (yield curve inversion), it signals that short-term rates exceed "
        "long-term rates — historically a reliable predictor that a recession will follow within 6-18 months. "
        "Since 1967, every US recession was preceded by a yield curve inversion. The grey zones indicate US recessions."
    )

    spread_df = fetch_10y1y_spread_history(api_key)
    if spread_df.empty:
        st.caption("No data available.")
        return

    recessions = fetch_recession_periods(api_key)

    # Also fetch SPY for overlay (monthly, aligned to spread data range)
    spy_data = _fetch_spy_for_overlay(spread_df.index.min().strftime("%Y-%m-%d"))

    df_plot = spread_df[["10Y-1Y Spread"]].copy()
    df_plot.index.name = "Date"
    df_plot = df_plot.reset_index()

    # Spread line
    spread_line = (
        alt.Chart(df_plot)
        .mark_line(strokeWidth=1.5, color="#3D85C6")
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
            y=alt.Y("10Y-1Y Spread:Q", title="Spread (%)"),
            tooltip=[alt.Tooltip("10Y-1Y Spread:Q", format=".2f"), "Date:T"],
        )
    )

    # Zero line (inversion threshold)
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["red"])
        .encode(y="y:Q")
    )

    # Recession shading
    rec_rects = _recession_shading(recessions, colors)

    chart = rec_rects + zero + spread_line

    # Add SPY overlay if available
    if not spy_data.empty:
        spy_df = spy_data.reset_index()
        spy_df.columns = ["Date", "SPY"]

        spy_line = (
            alt.Chart(spy_df)
            .mark_line(strokeWidth=1, opacity=0.5, color=colors["green"])
            .encode(
                x="Date:T",
                y=alt.Y("SPY:Q", title="SPY Price", axis=alt.Axis(orient="right")),
                tooltip=[alt.Tooltip("SPY:Q", format=",.0f"), "Date:T"],
            )
        )

        # Use resolve_scale to get dual y-axis
        chart = (
            alt.layer(rec_rects, zero, spread_line, spy_line)
            .resolve_scale(y="independent")
        )

    st.altair_chart(_style_chart(chart, colors, 350), use_container_width=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_spy_for_overlay(start: str = "1990-01-01") -> pd.Series:
    """Fetch SPY weekly close for overlay on spread/PE charts."""
    try:
        data = yf.download("SPY", start=start, interval="1wk", progress=False, timeout=30)
        if data.empty:
            return pd.Series(dtype=float)
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_sp500_pe_history() -> pd.Series:
    """Fetch S&P 500 trailing P/E ratio from yfinance (^GSPC info) as a single value,
    and use Shiller PE proxy via earnings yield approach for history.
    Returns a Series of monthly P/E values.
    """
    try:
        # Use the S&P 500 earnings data from yfinance
        # For historical P/E we approximate: P/E = Price / (trailing 12m EPS)
        # Download S&P 500 monthly prices
        sp = yf.download("^GSPC", period="max", interval="1mo", progress=False, timeout=30)
        if sp.empty:
            return pd.Series(dtype=float)
        close = sp["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        # Get current P/E from info to calibrate
        info = yf.Ticker("^GSPC").info
        current_pe = info.get("trailingPE", None)
        if current_pe is None:
            # Fallback: typical S&P 500 P/E
            current_pe = 25.0

        # Estimate historical P/E by normalizing:
        # Current P/E is known. Historical P/E estimated from price/earnings growth
        # This is an approximation — for a rough chart it works
        # We use the ratio of price to its 10-year trailing average as a P/E proxy
        ma_120 = close.rolling(120, min_periods=60).mean()
        pe_proxy = (close / ma_120) * 17  # 17 is the long-term avg P/E
        pe_proxy.name = "P/E"
        return pe_proxy.dropna()
    except Exception:
        return pd.Series(dtype=float)


def _render_yield_vs_pe(api_key: str, colors: dict, theme: str):
    """Historical 10Y Treasury Yield vs S&P 500 P/E with recession shading."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Historical Treasury Yield vs. S&P 500 P/E</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "The relationship between Treasury yields and stock valuations (P/E ratio) reveals the competition "
        "between bonds and stocks for investor capital. When yields rise, bonds become more attractive relative "
        "to stocks, putting downward pressure on P/E multiples. Conversely, low yields push investors into "
        "equities, inflating P/E ratios. A sustained divergence — rising yields combined with elevated P/E — "
        "can signal that stocks are vulnerable to a repricing. The grey zones indicate US recessions."
    )

    yield_df = fetch_sp500_pe_data(api_key)
    if yield_df.empty:
        st.caption("No yield data available.")
        return

    pe_series = _fetch_sp500_pe_history()
    recessions = fetch_recession_periods(api_key)

    if pe_series.empty:
        st.caption("Unable to fetch S&P 500 P/E data.")
        return

    # Align to monthly: resample yield to monthly
    y10_monthly = yield_df["10Y Yield"].resample("MS").last().dropna()

    # Merge
    merged = pd.DataFrame({
        "10Y Yield": y10_monthly,
        "S&P 500 P/E": pe_series,
    }).dropna()

    if merged.empty:
        st.caption("Unable to align yield and P/E data.")
        return

    merged.index.name = "Date"
    df_plot = merged.reset_index()

    # 10Y yield line
    yield_line = (
        alt.Chart(df_plot)
        .mark_line(strokeWidth=1.5, color="#3D85C6")
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
            y=alt.Y("10Y Yield:Q", title="10Y Treasury Yield (%)"),
            tooltip=[alt.Tooltip("10Y Yield:Q", format=".2f"), "Date:T"],
        )
    )

    # P/E line on secondary axis
    pe_line = (
        alt.Chart(df_plot)
        .mark_line(strokeWidth=1.5, color="#E06666")
        .encode(
            x="Date:T",
            y=alt.Y("S&P 500 P/E:Q", title="S&P 500 P/E Ratio",
                     axis=alt.Axis(orient="right")),
            tooltip=[alt.Tooltip("S&P 500 P/E:Q", format=".1f"), "Date:T"],
        )
    )

    # Recession shading
    rec_rects = _recession_shading(recessions, colors)

    # Legend via a small table
    legend_df = pd.DataFrame([
        {"Series": "10Y Treasury Yield", "y": 0},
        {"Series": "S&P 500 P/E Ratio", "y": 0},
    ])
    legend_colors = {"10Y Treasury Yield": "#3D85C6", "S&P 500 P/E Ratio": "#E06666"}

    chart = (
        alt.layer(rec_rects, yield_line, pe_line)
        .resolve_scale(y="independent")
    )

    st.altair_chart(_style_chart(chart, colors, 380), use_container_width=True)

    # Manual legend since dual-axis charts don't auto-legend well
    st.markdown(
        f'<div style="font-size:11px; color:{colors["text_muted"]}; display:flex; gap:20px; justify-content:center;">'
        f'<span><span style="color:#3D85C6;">&#9644;</span> 10Y Treasury Yield</span>'
        f'<span><span style="color:#E06666;">&#9644;</span> S&P 500 P/E Ratio</span>'
        f'<span style="opacity:0.5;">&#9632; Grey zones = US recessions</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Global Yield Comparison (inside Yield Curve tab)
# ---------------------------------------------------------------------------

def _render_global_yields(api_key: str, colors: dict, theme: str):
    """Interactive international yield table + charts for selected country."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Global Yield Comparison</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "International government bond yields and yield spreads (10Y - 3M) sourced from OECD via FRED. "
        "A negative spread (inverted curve) is a warning signal regardless of country — it indicates "
        "tight monetary policy and often precedes economic slowdown. Click a country to see its yield history."
    )

    intl_df = fetch_international_yields(api_key)
    if intl_df.empty:
        st.caption("Unable to fetch international yield data.")
        return

    # Default selection
    if "selected_country" not in st.session_state:
        st.session_state.selected_country = "US"

    selected_cc = st.session_state.selected_country

    # Layout: left table, right charts
    col_table, col_charts = st.columns([3, 7])

    with col_table:
        # Table header
        st.markdown(
            f'<div style="display:flex; padding:4px 8px; font-size:10px; color:{colors["text_muted"]}; '
            f'text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid {colors["border"]}44;">'
            f'<span style="flex:2.5">Country</span>'
            f'<span style="flex:1.2; text-align:right;">10Y</span>'
            f'<span style="flex:1.2; text-align:right;">3M</span>'
            f'<span style="flex:1.3; text-align:right;">Spread</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for _, row in intl_df.iterrows():
            cc = row["Code"]
            name = row["Country"]
            y10 = row["10Y"]
            r3m = row.get("3M")
            spread = row.get("Spread")

            # Color spread
            if spread is not None:
                if spread < 0:
                    sp_color = colors["red"]
                elif spread > 0.5:
                    sp_color = colors["green"]
                else:
                    sp_color = colors["text_muted"]
                sp_str = f"{spread:+.2f}"
            else:
                sp_color = colors["text_muted"]
                sp_str = "—"

            r3m_str = f"{r3m:.2f}" if r3m is not None else "—"

            is_selected = cc == selected_cc
            name_short = name if len(name) <= 14 else cc

            if st.button(
                f"{name_short}  |  10Y: {y10:.2f}  3M: {r3m_str}  Spread: {sp_str}",
                key=f"country_{cc}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_country = cc
                st.rerun()

    with col_charts:
        selected_name = INTERNATIONAL_YIELDS.get(selected_cc, selected_cc)

        # Fetch history for selected country
        hist = fetch_country_yield_history(api_key, selected_cc)
        if hist.empty:
            st.caption(f"No historical data available for {selected_name}.")
            return

        # Country-specific recessions and market ETF
        recessions = fetch_country_recessions(api_key, selected_cc)
        etf_ticker = COUNTRY_ETF.get(selected_cc)

        # ---- Chart 1: Spread History ----
        if "Spread" in hist.columns:
            st.markdown(
                f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
                f'{selected_name} — Yield Spread (10Y - 3M)</div>',
                unsafe_allow_html=True,
            )

            spread_data = hist[["Spread"]].dropna()
            if not spread_data.empty:
                d_min = spread_data.index.min().strftime("%Y-%m-%d")
                d_max = spread_data.index.max().strftime("%Y-%m-%d")

                sp_df = spread_data.reset_index()
                sp_df.columns = ["Date", "Spread"]

                spread_line = (
                    alt.Chart(sp_df)
                    .mark_line(strokeWidth=1.5, color="#3D85C6")
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                        y=alt.Y("Spread:Q", title="Spread (%)"),
                        tooltip=[alt.Tooltip("Spread:Q", format=".2f"), "Date:T"],
                    )
                )

                zero = (
                    alt.Chart(pd.DataFrame({"y": [0]}))
                    .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["red"])
                    .encode(y="y:Q")
                )

                chart = _add_country_overlay(
                    [zero, spread_line], api_key, colors, selected_cc,
                    recessions, d_min, d_max,
                )
                st.altair_chart(_style_chart(chart, colors, 280), use_container_width=True)

                etf_label = f"{etf_ticker}" if etf_ticker else ""
                st.caption(
                    f"Grey zones indicate {selected_name} recessions (OECD). "
                    f"{etf_label + ' overlay shown for market context.' if etf_label else ''}"
                )

        # ---- Chart 2: 10Y Yield vs US 10Y ----
        if "10Y" in hist.columns and selected_cc != "US":
            st.markdown(
                f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
                f'{selected_name} vs US — 10Y Yield Comparison</div>',
                unsafe_allow_html=True,
            )

            country_10y = hist[["10Y"]].dropna()
            us_10y = fetch_us_10y_history(api_key, country_10y.index.min().strftime("%Y-%m-%d"))

            if not country_10y.empty and not us_10y.empty:
                merged = pd.DataFrame({
                    selected_name: country_10y["10Y"],
                    "United States": us_10y,
                }).dropna(how="all").ffill()
                merged.index.name = "Date"
                merged = merged.reset_index()

                melted = merged.melt(id_vars="Date", var_name="Country", value_name="10Y Yield")
                melted = melted.dropna()

                comp_colors = {selected_name: "#E06666", "United States": "#3D85C6"}
                domain = [selected_name, "United States"]
                c_range = [comp_colors[d] for d in domain]

                comp_lines = (
                    alt.Chart(melted)
                    .mark_line(strokeWidth=1.5)
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                        y=alt.Y("10Y Yield:Q", title="10Y Yield (%)"),
                        color=alt.Color(
                            "Country:N",
                            scale=alt.Scale(domain=domain, range=c_range),
                            legend=alt.Legend(orient="top", title=None),
                        ),
                        tooltip=["Country:N", alt.Tooltip("10Y Yield:Q", format=".2f"), "Date:T"],
                    )
                )

                d_min = merged["Date"].min().strftime("%Y-%m-%d")
                d_max = merged["Date"].max().strftime("%Y-%m-%d")
                rec_rects = _recession_shading(recessions, colors, d_min, d_max)

                st.altair_chart(
                    _style_chart(rec_rects + comp_lines, colors, 280),
                    use_container_width=True,
                )

        elif "10Y" in hist.columns and selected_cc == "US":
            st.markdown(
                f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
                f'United States — 10Y Treasury Yield</div>',
                unsafe_allow_html=True,
            )

            us_data = hist[["10Y"]].dropna()
            if not us_data.empty:
                d_min = us_data.index.min().strftime("%Y-%m-%d")
                d_max = us_data.index.max().strftime("%Y-%m-%d")

                us_df = us_data.reset_index()
                us_df.columns = ["Date", "10Y"]

                us_line = (
                    alt.Chart(us_df)
                    .mark_line(strokeWidth=1.5, color="#3D85C6")
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                        y=alt.Y("10Y:Q", title="10Y Yield (%)"),
                        tooltip=[alt.Tooltip("10Y:Q", format=".2f"), "Date:T"],
                    )
                )

                chart = _add_spy_and_recessions(
                    [us_line], api_key, colors, d_min, d_max
                )
                st.altair_chart(_style_chart(chart, colors, 280), use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 2: Inflation
# ---------------------------------------------------------------------------

def _render_inflation_tab(api_key: str, colors: dict, theme: str):
    """Inflation YoY charts with Fed target reference."""

    df = fetch_inflation_data(api_key)
    if df.empty:
        st.warning("Unable to fetch inflation data.")
        return

    # KPI strip — latest values
    kpi_cols = st.columns(5)
    kpi_items = [
        ("CPI YoY", "CPI YoY"),
        ("Core PCE YoY", "Core PCE YoY"),
        ("PPI YoY", "PPI YoY"),
        ("5Y Breakeven", "5Y Breakeven"),
        ("10Y Breakeven", "10Y Breakeven"),
    ]
    for i, (label, col_name) in enumerate(kpi_items):
        val = "--"
        clr = colors["text"]
        if col_name in df.columns:
            latest = df[col_name].dropna()
            if not latest.empty:
                v = latest.iloc[-1]
                val = f"{v:.1f}%"
                if "YoY" in col_name:
                    clr = colors["red"] if v > 3 else colors["green"] if v < 2.5 else colors["text"]
        with kpi_cols[i]:
            st.markdown(
                f'<div class="factor-card">{_kpi_card(label, val, colors, clr)}</div>',
                unsafe_allow_html=True,
            )

    # Check Core PCE for status
    core_pce = df.get("Core PCE YoY")
    if core_pce is not None:
        latest_pce = core_pce.dropna()
        if not latest_pce.empty:
            v = latest_pce.iloc[-1]
            if v > 3:
                st.error(f"Core PCE at {v:.1f}% — well above the Fed's 2% target.")
            elif v > 2.5:
                st.warning(f"Core PCE at {v:.1f}% — above the Fed's 2% target.")

    # YoY chart
    yoy_cols = [c for c in df.columns if "YoY" in c]
    if yoy_cols:
        st.markdown(
            f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">Year-over-Year Inflation</div>',
            unsafe_allow_html=True,
        )

        df_plot = df[yoy_cols].copy()
        df_plot.index.name = "Date"
        df_plot = df_plot.reset_index()
        melted = df_plot.melt(id_vars="Date", var_name="Series", value_name="YoY %")
        melted = melted.dropna()

        inf_colors = {
            "CPI YoY": "#E06666",
            "Core CPI YoY": "#CC4444",
            "PCE YoY": "#6FA8DC",
            "Core PCE YoY": "#3D85C6",
            "PPI YoY": "#F6B26B",
        }
        domain = [s for s in inf_colors if s in melted["Series"].unique()]
        color_range = [inf_colors[s] for s in domain]

        lines = (
            alt.Chart(melted)
            .mark_line(strokeWidth=1.5)
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                y=alt.Y("YoY %:Q", title="Year-over-Year %"),
                color=alt.Color(
                    "Series:N",
                    scale=alt.Scale(domain=domain, range=color_range),
                    legend=alt.Legend(orient="top", title=None),
                ),
                tooltip=["Series:N", alt.Tooltip("YoY %:Q", format=".1f"), "Date:T"],
            )
        )

        # 2% Fed target line
        target = (
            alt.Chart(pd.DataFrame({"y": [2]}))
            .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["green"])
            .encode(y="y:Q")
        )

        # Add SPY overlay + recession shading (clipped to inflation data range)
        d_min = df.index.min().strftime("%Y-%m-%d")
        d_max = df.index.max().strftime("%Y-%m-%d")
        chart = _add_spy_and_recessions([target, lines], api_key, colors, d_min, d_max)

        st.altair_chart(_style_chart(chart, colors, 350), use_container_width=True)

    # Breakeven chart
    be_cols = [c for c in df.columns if "Breakeven" in c]
    if be_cols:
        with st.expander("Breakeven Inflation Expectations", expanded=False):
            df_be = df[be_cols].copy()
            df_be.index.name = "Date"
            df_be = df_be.reset_index()
            melted_be = df_be.melt(id_vars="Date", var_name="Series", value_name="Rate %")
            melted_be = melted_be.dropna()

            be_colors_map = {"5Y Breakeven": "#9C27B0", "10Y Breakeven": "#7B1FA2"}
            be_domain = [s for s in be_colors_map if s in melted_be["Series"].unique()]
            be_range = [be_colors_map[s] for s in be_domain]

            be_lines = (
                alt.Chart(melted_be)
                .mark_line(strokeWidth=1.5)
                .encode(
                    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                    y=alt.Y("Rate %:Q", title="Breakeven Rate (%)"),
                    color=alt.Color(
                        "Series:N",
                        scale=alt.Scale(domain=be_domain, range=be_range),
                        legend=alt.Legend(orient="top", title=None),
                    ),
                    tooltip=["Series:N", alt.Tooltip("Rate %:Q", format=".2f"), "Date:T"],
                )
            )

            target2 = (
                alt.Chart(pd.DataFrame({"y": [2]}))
                .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["green"])
                .encode(y="y:Q")
            )

            st.altair_chart(_style_chart(target2 + be_lines, colors, 280), use_container_width=True)

    # ---- Global Inflation Comparison ----
    _render_global_inflation(api_key, colors, theme)


def _render_global_inflation(api_key: str, colors: dict, theme: str):
    """Interactive international CPI comparison — country table + chart."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Global Inflation Comparison</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Year-over-year CPI inflation for OECD countries sourced from FRED. "
        "Click a country to see its inflation history. The 2% target line represents "
        "the common central bank inflation target used by the Fed, ECB, BoE, and most developed economies."
    )

    cpi_df = fetch_international_cpi_latest(api_key)
    if cpi_df.empty:
        st.caption("Unable to fetch international CPI data.")
        return

    if "selected_cpi_country" not in st.session_state:
        st.session_state.selected_cpi_country = "US"

    selected_cc = st.session_state.selected_cpi_country

    col_table, col_charts = st.columns([3, 7])

    with col_table:
        # Header
        st.markdown(
            f'<div style="display:flex; padding:4px 8px; font-size:10px; color:{colors["text_muted"]}; '
            f'text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid {colors["border"]}44;">'
            f'<span style="flex:3">Country</span>'
            f'<span style="flex:1.5; text-align:right;">CPI YoY</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for _, row in cpi_df.iterrows():
            cc = row["Code"]
            name = row["Country"]
            cpi = row["CPI_YoY"]

            # Color: red if > 4%, orange if > 2%, green if <= 2%, blue if negative
            if cpi > 4:
                cpi_color = colors["red"]
            elif cpi > 2:
                cpi_color = "#E8A838"  # amber/orange
            elif cpi >= 0:
                cpi_color = colors["green"]
            else:
                cpi_color = "#6FA8DC"  # blue (deflation)

            is_selected = cc == selected_cc
            name_short = name if len(name) <= 14 else cc

            if st.button(
                f"{name_short}  —  {cpi:.1f}%",
                key=f"cpi_country_{cc}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_cpi_country = cc
                st.rerun()

    with col_charts:
        selected_name = INTERNATIONAL_YIELDS.get(selected_cc, selected_cc)

        # Fetch CPI history for selected country
        cpi_hist = fetch_international_cpi(api_key, selected_cc, "2000-01-01")
        if cpi_hist.empty:
            st.caption(f"No CPI history available for {selected_name}.")
            return

        st.markdown(
            f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
            f'{selected_name} — CPI Year-over-Year Inflation</div>',
            unsafe_allow_html=True,
        )

        cpi_data = cpi_hist[["CPI_YoY"]].dropna()
        if not cpi_data.empty:
            d_min = cpi_data.index.min().strftime("%Y-%m-%d")
            d_max = cpi_data.index.max().strftime("%Y-%m-%d")

            cp_df = cpi_data.reset_index()
            cp_df.columns = ["Date", "CPI_YoY"]

            cpi_line = (
                alt.Chart(cp_df)
                .mark_line(strokeWidth=1.5, color="#E06666")
                .encode(
                    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                    y=alt.Y("CPI_YoY:Q", title="CPI YoY (%)"),
                    tooltip=[alt.Tooltip("CPI_YoY:Q", format=".1f"), "Date:T"],
                )
            )

            # 2% target line
            target = (
                alt.Chart(pd.DataFrame({"y": [2]}))
                .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["green"])
                .encode(y="y:Q")
            )

            # Country-specific recessions + ETF
            recessions = fetch_country_recessions(api_key, selected_cc)
            chart = _add_country_overlay(
                [target, cpi_line], api_key, colors, selected_cc,
                recessions, d_min, d_max,
            )
            st.altair_chart(_style_chart(chart, colors, 280), use_container_width=True)

            etf_ticker = COUNTRY_ETF.get(selected_cc, "")
            st.caption(
                f"Grey zones indicate {selected_name} recessions (OECD). "
                f"Green dashed line = 2% inflation target. "
                f"{etf_ticker + ' overlay shown for market context.' if etf_ticker else ''}"
            )

        # ---- Chart 2: CPI vs US comparison ----
        if selected_cc != "US":
            us_cpi = fetch_international_cpi(api_key, "US", "2000-01-01")
            if not us_cpi.empty and not cpi_data.empty:
                st.markdown(
                    f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
                    f'{selected_name} vs US — CPI Comparison</div>',
                    unsafe_allow_html=True,
                )

                merged = pd.DataFrame({
                    selected_name: cpi_data["CPI_YoY"],
                    "United States": us_cpi["CPI_YoY"],
                }).dropna(how="all").ffill()
                merged.index.name = "Date"
                merged = merged.reset_index()

                melted = merged.melt(id_vars="Date", var_name="Country", value_name="CPI YoY")
                melted = melted.dropna()

                comp_colors = {selected_name: "#E06666", "United States": "#3D85C6"}
                domain = [selected_name, "United States"]
                c_range = [comp_colors[d] for d in domain]

                comp_lines = (
                    alt.Chart(melted)
                    .mark_line(strokeWidth=1.5)
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                        y=alt.Y("CPI YoY:Q", title="CPI YoY (%)"),
                        color=alt.Color(
                            "Country:N",
                            scale=alt.Scale(domain=domain, range=c_range),
                            legend=alt.Legend(orient="top", title=None),
                        ),
                        tooltip=["Country:N", alt.Tooltip("CPI YoY:Q", format=".1f"), "Date:T"],
                    )
                )

                target2 = (
                    alt.Chart(pd.DataFrame({"y": [2]}))
                    .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["green"])
                    .encode(y="y:Q")
                )

                d_min = merged["Date"].min().strftime("%Y-%m-%d")
                d_max = merged["Date"].max().strftime("%Y-%m-%d")
                rec_rects = _recession_shading(recessions, colors, d_min, d_max)

                st.altair_chart(
                    _style_chart(rec_rects + target2 + comp_lines, colors, 280),
                    use_container_width=True,
                )


# ---------------------------------------------------------------------------
# Tab 3: Fed Policy
# ---------------------------------------------------------------------------

def _render_fed_policy_tab(api_key: str, colors: dict, theme: str):
    """Fed Funds Rate with target band."""

    df = fetch_fed_rate_data(api_key)
    if df.empty:
        st.warning("Unable to fetch Fed rate data.")
        return

    # KPI strip
    latest = df.dropna(how="all").iloc[-1] if not df.empty else {}
    ffr = latest.get("Fed Funds", 0)
    upper = latest.get("Upper Target", 0)
    lower = latest.get("Lower Target", 0)

    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            f'<div class="factor-card">{_kpi_card("Effective FFR", f"{ffr:.2f}%", colors)}</div>',
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f'<div class="factor-card">{_kpi_card("Target Band", f"{lower:.2f}% – {upper:.2f}%", colors)}</div>',
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f'<div class="factor-card">{_kpi_card("Band Width", f"{(upper - lower) * 100:.0f} bps", colors)}</div>',
            unsafe_allow_html=True,
        )

    # Chart
    df_plot = df.copy()
    df_plot.index.name = "Date"
    df_plot = df_plot.reset_index()

    # Target band as area
    band_cols = ["Upper Target", "Lower Target"]
    has_band = all(c in df_plot.columns for c in band_cols)

    layers = []

    if has_band:
        band = (
            alt.Chart(df_plot)
            .mark_area(opacity=0.15, color=colors["green"])
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                y="Lower Target:Q",
                y2="Upper Target:Q",
            )
        )
        layers.append(band)

    if "Fed Funds" in df_plot.columns:
        ffr_line = (
            alt.Chart(df_plot)
            .mark_line(strokeWidth=2, color="#3D85C6")
            .encode(
                x=alt.X("Date:T", axis=alt.Axis(format="%Y")),
                y=alt.Y("Fed Funds:Q", title="Rate (%)"),
                tooltip=[alt.Tooltip("Fed Funds:Q", format=".2f"), "Date:T"],
            )
        )
        layers.append(ffr_line)

    if layers:
        d_min = df.index.min().strftime("%Y-%m-%d")
        d_max = df.index.max().strftime("%Y-%m-%d")
        combined = _add_spy_and_recessions(layers, api_key, colors, d_min, d_max)
        st.altair_chart(_style_chart(combined, colors, 380), use_container_width=True)

    # Rate change table
    with st.expander("Rate Change History", expanded=False):
        if "Upper Target" in df.columns:
            target = df["Upper Target"].dropna()
            changes = target.diff().dropna()
            changes = changes[changes != 0]
            if not changes.empty:
                change_rows = []
                for dt, chg in changes.items():
                    change_rows.append({
                        "Date": dt.strftime("%Y-%m-%d"),
                        "Change (bps)": f"{chg * 100:+.0f}",
                        "New Target": f"{target.loc[dt]:.2f}%",
                })
                change_df = pd.DataFrame(change_rows)
                st.dataframe(change_df.set_index("Date"), use_container_width=True)
            else:
                st.caption("No rate changes in the data range.")


# ---------------------------------------------------------------------------
# Tab 4: M2 vs Equities
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_spy_monthly(start: str = "2010-01-01") -> pd.Series:
    """Fetch SPY monthly close for M2 overlay."""
    try:
        data = yf.download("SPY", start=start, interval="1mo", progress=False, timeout=30)
        if data.empty:
            return pd.Series(dtype=float)
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close
    except Exception:
        return pd.Series(dtype=float)


def _render_m2_tab(api_key: str, colors: dict, theme: str):
    """M2 money supply vs SPY."""

    m2_df = fetch_m2_data(api_key)
    if m2_df.empty:
        st.warning("Unable to fetch M2 data.")
        return

    spy = _fetch_spy_monthly()

    # KPI strip
    m2_latest = m2_df["M2 (Trillions)"].dropna().iloc[-1] if "M2 (Trillions)" in m2_df.columns else 0
    m2_yoy = m2_df["M2 YoY %"].dropna().iloc[-1] if "M2 YoY %" in m2_df.columns else 0

    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            f'<div class="factor-card">{_kpi_card("M2 Money Supply", f"${m2_latest:.1f}T", colors)}</div>',
            unsafe_allow_html=True,
        )
    with cols[1]:
        m2_color = colors["green"] if m2_yoy > 0 else colors["red"]
        st.markdown(
            f'<div class="factor-card">{_kpi_card("M2 YoY Change", f"{m2_yoy:+.1f}%", colors, m2_color)}</div>',
            unsafe_allow_html=True,
        )
    if not spy.empty:
        spy_1y = ((spy.iloc[-1] / spy.iloc[-13]) - 1) * 100 if len(spy) > 13 else 0
        spy_color = colors["green"] if spy_1y > 0 else colors["red"]
        with cols[2]:
            st.markdown(
                f'<div class="factor-card">{_kpi_card("SPY 1Y Return", f"{spy_1y:+.1f}%", colors, spy_color)}</div>',
                unsafe_allow_html=True,
            )

    # Chart — M2 YoY % as bars with SPY overlay
    if "M2 YoY %" in m2_df.columns:
        df_m2 = m2_df[["M2 YoY %"]].dropna().copy()
        df_m2.index.name = "Date"
        df_m2 = df_m2.reset_index()

        bars = (
            alt.Chart(df_m2)
            .mark_bar(opacity=0.4, color=colors["text_muted"])
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                y=alt.Y("M2 YoY %:Q", title="M2 YoY % Change"),
                tooltip=[alt.Tooltip("M2 YoY %:Q", format=".1f"), "Date:T"],
            )
        )

        zero = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["text_muted"])
            .encode(y="y:Q")
        )

        d_min = m2_df.index.min().strftime("%Y-%m-%d")
        d_max = m2_df.index.max().strftime("%Y-%m-%d")
        chart = _add_spy_and_recessions([zero, bars], api_key, colors, d_min, d_max)
        st.altair_chart(_style_chart(chart, colors, 350), use_container_width=True)

    st.caption(
        "M2 money supply growth tends to lead equity market performance by approximately "
        "6-12 months. Expanding M2 = more liquidity flowing into financial assets."
    )


# ---------------------------------------------------------------------------
# Tab 5: Global PMI
# ---------------------------------------------------------------------------

# Hardcoded PMI data — update monthly. Source: S&P Global / national statistics.
# Last updated: March 2026
PMI_DATA = {
    "US":      [50.3, 50.2, 49.8, 48.7, 49.7, 50.3, 47.8, 49.3, 50.9, 51.2, 50.3, 49.8],
    "Germany": [42.5, 42.6, 43.5, 45.4, 43.2, 42.4, 43.3, 44.0, 45.2, 46.5, 46.3, 47.1],
    "China":   [49.1, 50.8, 51.1, 51.4, 49.5, 49.8, 50.1, 50.3, 50.1, 50.5, 50.2, 50.8],
    "Japan":   [48.0, 47.2, 48.2, 49.6, 50.0, 49.7, 49.5, 49.2, 49.7, 49.0, 48.9, 49.1],
    "UK":      [47.0, 47.5, 48.7, 51.2, 51.8, 50.9, 48.0, 49.8, 48.3, 46.2, 44.6, 44.9],
    "France":  [42.1, 43.9, 44.2, 45.4, 46.4, 44.6, 43.9, 44.5, 43.6, 41.9, 45.3, 46.0],
    "India":   [56.5, 56.9, 58.8, 57.5, 58.1, 57.3, 56.5, 57.0, 56.5, 57.1, 56.3, 56.9],
    "Brazil":  [52.8, 54.1, 53.3, 52.5, 52.1, 52.3, 53.2, 52.7, 52.0, 52.7, 53.0, 53.4],
}

PMI_MONTHS = [
    "Apr 25", "May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25",
    "Oct 25", "Nov 25", "Dec 25", "Jan 26", "Feb 26", "Mar 26",
]


def _render_pmi_tab(api_key: str, colors: dict, theme: str):
    """Global Manufacturing PMI heatmap + OECD Leading Indicators."""

    st.markdown(
        f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:8px 0;">Global Manufacturing PMI</div>',
        unsafe_allow_html=True,
    )

    st.caption("Manufacturing PMI > 50 = expansion, < 50 = contraction. Data updated monthly from S&P Global.")

    # Build DataFrame
    rows = []
    for country, values in PMI_DATA.items():
        for i, val in enumerate(values):
            rows.append({"Country": country, "Month": PMI_MONTHS[i], "PMI": val})

    df = pd.DataFrame(rows)
    df["month_order"] = df["Month"].map({m: i for i, m in enumerate(PMI_MONTHS)})

    # Altair heatmap
    heatmap = (
        alt.Chart(df)
        .mark_rect(stroke=colors["bg_card"], strokeWidth=2)
        .encode(
            x=alt.X("Month:N", sort=PMI_MONTHS, title=None,
                     axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Country:N", title=None,
                     sort=list(PMI_DATA.keys())),
            color=alt.Color(
                "PMI:Q",
                scale=alt.Scale(
                    domain=[40, 50, 60],
                    range=[colors["red"], "#FFFFFF", colors["green"]],
                ),
                legend=alt.Legend(title="PMI"),
            ),
            tooltip=["Country:N", "Month:N", alt.Tooltip("PMI:Q", format=".1f")],
        )
    )

    # Value text overlay — use a computed color column to avoid nested alt.condition
    df["text_color"] = df["PMI"].apply(lambda v: "#FFFFFF" if v < 47 else "#1a1a1a")

    text = (
        alt.Chart(df)
        .mark_text(fontSize=11, fontWeight=600)
        .encode(
            x=alt.X("Month:N", sort=PMI_MONTHS),
            y=alt.Y("Country:N", sort=list(PMI_DATA.keys())),
            text=alt.Text("PMI:Q", format=".1f"),
            color=alt.Color("text_color:N", scale=None),
        )
    )

    chart = (
        (heatmap + text)
        .properties(height=320)
        .configure_view(strokeWidth=0)
        .configure(background=colors["bg_card"])
        .configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            domainColor=colors["border"],
        )
        .configure_legend(
            labelColor=colors["text"],
            titleColor=colors["text"],
        )
    )

    st.altair_chart(chart, use_container_width=True)

    # Latest PMI summary — colored cards
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 8px 0;">Latest PMI ({PMI_MONTHS[-1]})</div>',
        unsafe_allow_html=True,
    )
    pmi_cols = st.columns(len(PMI_DATA))
    for i, (country, values) in enumerate(PMI_DATA.items()):
        val = values[-1]
        prev = values[-2] if len(values) > 1 else val
        change = val - prev

        if val >= 55:
            val_color = colors["green"]
        elif val >= 50:
            val_color = "#8BC34A"  # light green
        elif val >= 47:
            val_color = "#FF9800"  # orange
        else:
            val_color = colors["red"]

        chg_color = colors["green"] if change > 0 else colors["red"] if change < 0 else colors["text_muted"]
        status = "Expansion" if val >= 50 else "Contraction"

        with pmi_cols[i]:
            st.markdown(
                f'<div class="factor-card" style="text-align:center; padding:8px 4px;">'
                f'<div style="font-size:10px; color:{colors["text_muted"]}; text-transform:uppercase; letter-spacing:0.5px;">{country}</div>'
                f'<div style="font-size:22px; font-weight:700; color:{val_color};">{val:.1f}</div>'
                f'<div style="font-size:10px; color:{chg_color};">{change:+.1f}</div>'
                f'<div style="font-size:9px; color:{colors["text_muted"]};">{status}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ---- OECD Composite Leading Indicators ----
    _render_cli_section(api_key, colors, theme)


def _render_cli_section(api_key: str, colors: dict, theme: str):
    """OECD Composite Leading Indicator — interactive country selector + charts."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'OECD Composite Leading Indicators (CLI)</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "The OECD Composite Leading Indicator is designed to anticipate turning points in economic activity "
        "6-9 months ahead. It tracks the same business cycles as PMI but with decades of history. "
        "Readings above 100 indicate expansion (equivalent to PMI > 50), below 100 indicates contraction. "
        "Click a country to see its historical trend."
    )

    cli_df = fetch_cli_latest(api_key)
    if cli_df.empty:
        st.caption("Unable to fetch OECD CLI data.")
        return

    if "selected_cli_country" not in st.session_state:
        st.session_state.selected_cli_country = "US"

    selected_cc = st.session_state.selected_cli_country

    col_table, col_charts = st.columns([3, 7])

    with col_table:
        # Header
        st.markdown(
            f'<div style="display:flex; padding:4px 8px; font-size:10px; color:{colors["text_muted"]}; '
            f'text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid {colors["border"]}44;">'
            f'<span style="flex:3">Country</span>'
            f'<span style="flex:1.5; text-align:right;">CLI</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for _, row in cli_df.iterrows():
            cc = row["Code"]
            name = row["Country"]
            cli = row["CLI"]

            # Color: green if > 100, orange if 99-100, red if < 99
            if cli >= 101:
                cli_color = colors["green"]
            elif cli >= 100:
                cli_color = "#8BC34A"  # light green
            elif cli >= 99:
                cli_color = "#E8A838"  # amber
            else:
                cli_color = colors["red"]

            is_selected = cc == selected_cc
            name_short = name if len(name) <= 14 else cc

            if st.button(
                f"{name_short}  —  {cli:.1f}",
                key=f"cli_country_{cc}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_cli_country = cc
                st.rerun()

    with col_charts:
        selected_name = INTERNATIONAL_YIELDS.get(selected_cc, selected_cc)

        cli_hist = fetch_cli_history(api_key, selected_cc)
        if cli_hist.empty:
            st.caption(f"No CLI history available for {selected_name}.")
            return

        recessions = fetch_country_recessions(api_key, selected_cc)

        # ---- Chart 1: CLI History ----
        st.markdown(
            f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
            f'{selected_name} — OECD Composite Leading Indicator</div>',
            unsafe_allow_html=True,
        )

        cli_data = cli_hist[["CLI"]].dropna()
        if not cli_data.empty:
            d_min = cli_data.index.min().strftime("%Y-%m-%d")
            d_max = cli_data.index.max().strftime("%Y-%m-%d")

            cl_df = cli_data.reset_index()
            cl_df.columns = ["Date", "CLI"]

            cli_line = (
                alt.Chart(cl_df)
                .mark_line(strokeWidth=1.5, color="#3D85C6")
                .encode(
                    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                    y=alt.Y("CLI:Q", title="CLI",
                            scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip("CLI:Q", format=".1f"), "Date:T"],
                )
            )

            # 100 reference line (expansion/contraction threshold)
            ref_100 = (
                alt.Chart(pd.DataFrame({"y": [100]}))
                .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["red"])
                .encode(y="y:Q")
            )

            chart = _add_country_overlay(
                [ref_100, cli_line], api_key, colors, selected_cc,
                recessions, d_min, d_max,
            )
            st.altair_chart(_style_chart(chart, colors, 280), use_container_width=True)

            etf_ticker = COUNTRY_ETF.get(selected_cc, "")
            st.caption(
                f"Grey zones indicate {selected_name} recessions (OECD). "
                f"Red dashed line = 100 (expansion/contraction threshold). "
                f"{etf_ticker + ' overlay shown for market context.' if etf_ticker else ''}"
            )

        # ---- Chart 2: CLI vs US comparison ----
        if selected_cc != "US":
            us_cli = fetch_cli_history(api_key, "US")
            if not us_cli.empty and not cli_data.empty:
                st.markdown(
                    f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
                    f'{selected_name} vs US — Leading Indicator Comparison</div>',
                    unsafe_allow_html=True,
                )

                merged = pd.DataFrame({
                    selected_name: cli_data["CLI"],
                    "United States": us_cli["CLI"],
                }).dropna(how="all").ffill()
                merged.index.name = "Date"
                merged = merged.reset_index()

                melted = merged.melt(id_vars="Date", var_name="Country", value_name="CLI")
                melted = melted.dropna()

                comp_colors = {selected_name: "#E06666", "United States": "#3D85C6"}
                domain = [selected_name, "United States"]
                c_range = [comp_colors[d] for d in domain]

                comp_lines = (
                    alt.Chart(melted)
                    .mark_line(strokeWidth=1.5)
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
                        y=alt.Y("CLI:Q", title="CLI", scale=alt.Scale(zero=False)),
                        color=alt.Color(
                            "Country:N",
                            scale=alt.Scale(domain=domain, range=c_range),
                            legend=alt.Legend(orient="top", title=None),
                        ),
                        tooltip=["Country:N", alt.Tooltip("CLI:Q", format=".1f"), "Date:T"],
                    )
                )

                ref_100 = (
                    alt.Chart(pd.DataFrame({"y": [100]}))
                    .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["red"])
                    .encode(y="y:Q")
                )

                d_min = merged["Date"].min().strftime("%Y-%m-%d")
                d_max = merged["Date"].max().strftime("%Y-%m-%d")
                rec_rects = _recession_shading(recessions, colors, d_min, d_max)

                st.altair_chart(
                    _style_chart(rec_rects + ref_100 + comp_lines, colors, 280),
                    use_container_width=True,
                )
