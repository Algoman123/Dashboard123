"""Fundamentals Dashboard — Earnings, Valuations, Insiders, Dividends, Analyst, IPOs."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from datetime import date, timedelta

from services.api_keys import get_finnhub_key, get_fmp_key


def _fmt_large_number(val) -> str:
    """Format large numbers: 1.5T, 391B, 12.3M, 5K."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    val = float(val)
    if abs(val) >= 1e12:
        return f"${val / 1e12:.1f}T"
    elif abs(val) >= 1e9:
        return f"${val / 1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"${val / 1e6:.1f}M"
    elif abs(val) >= 1e3:
        return f"${val / 1e3:.0f}K"
    else:
        return f"${val:,.0f}"
from services.fundamentals_dashboard_data import (
    SECTOR_ETFS,
    fetch_earnings_calendar,
    fetch_earnings_surprises,
    fetch_earnings_calendar_yf,
    fetch_sector_valuations,
    fetch_insider_transactions,
    fetch_insider_summary,
    fetch_dividend_data,
    fetch_analyst_recommendations,
    fetch_analyst_upgrades,
    fetch_price_target,
    fetch_ipo_calendar,
)


def render_fundamentals_dashboard(colors: dict, theme: str):
    """Render the full fundamentals dashboard."""

    # Header with refresh
    col_title, col_refresh = st.columns([9, 1])
    with col_title:
        st.markdown(
            f'<div style="text-align:center; margin-bottom:4px;">'
            f'<span style="font-size:28px; font-weight:700; color:{colors["text"]};">Fundamentals</span>'
            f'<br><span style="font-size:13px; color:{colors["text_muted"]};">'
            f'Earnings calendar, sector valuations, insider transactions, dividends & analyst revisions</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_refresh:
        if st.button("🔄", key="fund_dash_refresh", help="Refresh fundamentals data"):
            # Clear only fundamentals-related caches
            for fn in [fetch_earnings_calendar, fetch_earnings_surprises, fetch_earnings_calendar_yf]:
                fn.clear()
            st.rerun()

    finnhub_key = get_finnhub_key()
    fmp_key = get_fmp_key()

    tab_earn, tab_val, tab_insider, tab_div, tab_analyst, tab_ipo = st.tabs([
        "Earnings Calendar", "Sector Valuations", "Insider Transactions",
        "Dividends", "Analyst Revisions", "IPO Calendar",
    ])

    with tab_earn:
        _render_earnings_tab(finnhub_key, colors, theme)

    with tab_val:
        _render_sector_valuations_tab(fmp_key, colors, theme)

    with tab_insider:
        _render_insider_tab(finnhub_key, colors, theme)

    with tab_div:
        _render_dividends_tab(colors, theme)

    with tab_analyst:
        _render_analyst_tab(finnhub_key, colors, theme)

    with tab_ipo:
        _render_ipo_tab(finnhub_key, colors, theme)


def _build_portfolio_filter_options() -> dict[str, set[str] | None]:
    """Build dict of group name → ticker set for filtering.
    Returns None for 'All Stocks' (no filter).
    """
    options = {"All Stocks": None, "All Portfolio Tickers": set()}
    config = st.session_state.get("config", {})

    # Collect all portfolio tickers for the "All Portfolio" option
    all_portfolio = set()

    # Strategies
    strat_holdings = st.session_state.get("strategy_holdings", {})
    for strat in config.get("strategies", []):
        sid = strat["strategy_id"]
        name = strat.get("name", str(sid))
        holdings = strat_holdings.get(sid, [])
        if holdings:
            ticker_set = set(holdings)
            options[f"Strategy: {name}"] = ticker_set
            all_portfolio.update(ticker_set)

    # Screens
    screen_holdings = st.session_state.get("screen_holdings", {})
    for scr in config.get("screens", []):
        sid = scr["screen_id"]
        name = scr.get("name", str(sid))
        holdings = screen_holdings.get(sid, [])
        if holdings:
            ticker_set = set(holdings)
            options[f"Screen: {name}"] = ticker_set
            all_portfolio.update(ticker_set)

    # Rankings
    ranking_data = st.session_state.get("ranking_data", {})
    for rnk in config.get("rankings", []):
        rid = rnk["ranking_id"]
        name = rnk.get("name", str(rid))
        max_h = rnk.get("max_holdings", 25)
        holdings = ranking_data.get(rid, [])[:max_h]
        if holdings:
            ticker_set = set(holdings)
            options[f"Ranking: {name}"] = ticker_set
            all_portfolio.update(ticker_set)

    # Custom groups
    for group in config.get("custom_groups", []):
        name = group.get("name", "")
        tickers = group.get("tickers", [])
        if tickers:
            ticker_set = set(tickers)
            options[f"Custom: {name}"] = ticker_set
            all_portfolio.update(ticker_set)

    # Update "All Portfolio" with collected tickers
    if all_portfolio:
        options["All Portfolio Tickers"] = all_portfolio
    else:
        del options["All Portfolio Tickers"]

    return options


def _placeholder(colors: dict, title: str, description: str):
    """Placeholder for unimplemented tabs."""
    st.markdown(
        f'<div style="text-align:center; padding:40px; color:{colors["text_muted"]};">'
        f'<div style="font-size:16px; font-weight:600; margin-bottom:8px;">{title}</div>'
        f'<div style="font-size:13px;">{description}</div>'
        f'<div style="font-size:12px; margin-top:12px; opacity:0.6;">Coming soon</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tab 1: Earnings Calendar & Surprise Tracker
# ---------------------------------------------------------------------------

def _render_earnings_tab(finnhub_key: str | None, colors: dict, theme: str):
    """Earnings calendar and EPS surprise tracker."""

    if not finnhub_key:
        st.warning(
            "Add a Finnhub API key in ⚙️ Settings → API Settings for full earnings data. "
            "Get a free key at [finnhub.io](https://finnhub.io/register). "
            "Showing portfolio earnings dates from yfinance as fallback."
        )
        _render_earnings_yf_fallback(colors, theme)
        return

    st.caption(
        "Upcoming earnings reports with EPS/revenue estimates. Select a ticker to see its earnings surprise history. "
        "Data from Finnhub free API."
    )

    # Date range selector
    col_range, col_info = st.columns([3, 7])
    with col_range:
        range_sel = st.radio(
            "Date range",
            ["This Week", "Next 2 Weeks", "Next Month"],
            index=1,
            key="earn_range",
            horizontal=True,
        )

    today = date.today()
    if range_sel == "This Week":
        # Monday to Friday of current week
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif range_sel == "Next 2 Weeks":
        start = today
        end = today + timedelta(days=14)
    else:
        start = today
        end = today + timedelta(days=30)

    with st.spinner("Fetching earnings calendar..."):
        cal_df = fetch_earnings_calendar(finnhub_key, start.isoformat(), end.isoformat())

    # Supplement with yfinance for international portfolio tickers not in Finnhub
    intl_df = _fetch_international_portfolio_earnings(cal_df, start, end)
    if not intl_df.empty:
        cal_df = pd.concat([cal_df, intl_df], ignore_index=True)
        cal_df = cal_df.sort_values("Date")

    if cal_df.empty:
        st.info("No earnings data available for the selected period.")
        return

    with col_info:
        intl_count = len(intl_df) if not intl_df.empty else 0
        intl_note = f" (incl. {intl_count} international)" if intl_count > 0 else ""
        st.caption(f"Showing {len(cal_df)} earnings reports{intl_note} from {start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}")

    # ---- Filter controls ----
    col_group, col_search = st.columns([2, 2])

    with col_group:
        group_options = _build_portfolio_filter_options()
        group_names = list(group_options.keys())
        selected_group = st.selectbox(
            "Filter by portfolio group",
            group_names,
            index=0,
            key="earn_group_filter",
        )

    with col_search:
        search = st.text_input("Search ticker", "", key="earn_search", placeholder="Filter by ticker...")

    # Apply group filter
    group_tickers = group_options[selected_group]
    if group_tickers is not None:
        cal_df = cal_df[cal_df["Ticker"].isin(group_tickers)]

    # Apply search filter
    if search:
        cal_df = cal_df[cal_df["Ticker"].str.contains(search.upper(), na=False)]

    if cal_df.empty:
        if group_tickers is not None:
            st.info(f"No upcoming earnings for tickers in '{selected_group}' during this period.")
        else:
            st.info("No matching earnings found.")
        return

    # Update count after filtering
    st.caption(f"Showing {len(cal_df)} earnings reports")

    # ---- Earnings Calendar Table ----
    _render_earnings_table(cal_df, colors)

    # ---- Surprise Tracker ----
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Earnings Surprise Tracker</div>',
        unsafe_allow_html=True,
    )

    # Ticker selector — from calendar or manual
    all_tickers = sorted(cal_df["Ticker"].dropna().unique().tolist()) if not cal_df.empty else []
    col_sel, col_manual = st.columns([2, 2])
    with col_sel:
        selected = st.selectbox(
            "Select from calendar",
            [""] + all_tickers,
            index=0,
            key="earn_surprise_select",
        )
    with col_manual:
        manual = st.text_input("Or enter ticker", "", key="earn_surprise_manual", placeholder="e.g. AAPL")

    ticker = manual.upper().strip() if manual else selected

    if ticker:
        with st.spinner(f"Fetching earnings history for {ticker}..."):
            surprises = fetch_earnings_surprises(ticker, finnhub_key)

        if surprises.empty:
            st.caption(f"No earnings surprise data available for {ticker}.")
        else:
            _render_surprise_chart(ticker, surprises, colors, theme)


def _fetch_international_portfolio_earnings(finnhub_df: pd.DataFrame,
                                              start: date, end: date) -> pd.DataFrame:
    """Fetch earnings dates for international portfolio tickers not covered by Finnhub (US-only).

    Identifies tickers with exchange suffixes (.ST, .OL, .DE, .L, etc.) from portfolio holdings,
    checks yfinance for their earnings dates, and returns a DataFrame matching Finnhub's format.
    """
    from components.sidebar import collect_all_tickers

    config = st.session_state.get("config", {})
    all_tickers = collect_all_tickers(config)

    if not all_tickers:
        return pd.DataFrame()

    # International tickers have dots (exchange suffixes) — e.g., NOVO-B.ST, ASML.AS
    intl_tickers = [t for t in all_tickers if "." in t and not t.startswith("^")]

    if not intl_tickers:
        return pd.DataFrame()

    # Skip tickers already in Finnhub data
    if not finnhub_df.empty and "Ticker" in finnhub_df.columns:
        existing = set(finnhub_df["Ticker"].dropna().tolist())
        intl_tickers = [t for t in intl_tickers if t not in existing]

    if not intl_tickers:
        return pd.DataFrame()

    # Fetch from yfinance (cached separately)
    yf_df = fetch_earnings_calendar_yf(tuple(sorted(intl_tickers)))
    if yf_df.empty:
        return pd.DataFrame()

    # Filter to date range
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    yf_df = yf_df[(yf_df["Date"] >= start_ts) & (yf_df["Date"] <= end_ts)]

    if yf_df.empty:
        return pd.DataFrame()

    # Format to match Finnhub calendar columns
    result = pd.DataFrame({
        "Date": yf_df["Date"],
        "Ticker": yf_df["Ticker"],
        "Time": "",
        "EPS_Est": None,
        "EPS_Actual": None,
        "Rev_Est": None,
        "Rev_Actual": None,
        "Quarter": None,
    })
    return result


def _render_earnings_table(df: pd.DataFrame, colors: dict):
    """Render earnings calendar as HTML table."""

    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:1.2">Date</span>'
        '<span style="flex:0.8">Ticker</span>'
        '<span style="flex:0.8;text-align:center">Time</span>'
        '<span style="flex:1;text-align:right">EPS Est</span>'
        '<span style="flex:1;text-align:right">EPS Act</span>'
        '<span style="flex:1.2;text-align:right">Rev Est</span>'
        '<span style="flex:1.2;text-align:right">Rev Act</span>'
        '<span style="flex:0.6;text-align:center">Qtr</span>'
        '</div>'
    )

    rows_html = []
    for _, row in df.iterrows():
        date_str = row["Date"].strftime("%b %d") if pd.notna(row.get("Date")) else "—"
        ticker = row.get("Ticker", "—")
        time_str = row.get("Time", "")
        eps_est = row.get("EPS_Est")
        eps_act = row.get("EPS_Actual")
        rev_est = row.get("Rev_Est")
        rev_act = row.get("Rev_Actual")
        qtr = f"Q{row.get('Quarter', '')}" if pd.notna(row.get("Quarter")) else ""

        # Format values
        eps_est_str = f"${eps_est:.2f}" if pd.notna(eps_est) else "—"
        eps_act_str = f"${eps_act:.2f}" if pd.notna(eps_act) else "—"
        rev_est_str = _fmt_revenue(rev_est) if pd.notna(rev_est) else "—"
        rev_act_str = _fmt_revenue(rev_act) if pd.notna(rev_act) else "—"

        # Color EPS actual: green if beat, red if miss
        eps_clr = colors["text"]
        if pd.notna(eps_act) and pd.notna(eps_est):
            eps_clr = colors["green"] if eps_act >= eps_est else colors["red"]

        cells = (
            f'<span style="flex:1.2;color:{colors["text_muted"]}">{date_str}</span>'
            f'<span style="flex:0.8;font-weight:600">{ticker}</span>'
            f'<span style="flex:0.8;text-align:center;font-size:10px;color:{colors["text_muted"]}">{time_str}</span>'
            f'<span style="flex:1;text-align:right">{eps_est_str}</span>'
            f'<span style="flex:1;text-align:right;color:{eps_clr}">{eps_act_str}</span>'
            f'<span style="flex:1.2;text-align:right">{rev_est_str}</span>'
            f'<span style="flex:1.2;text-align:right">{rev_act_str}</span>'
            f'<span style="flex:0.6;text-align:center;font-size:10px;color:{colors["text_muted"]}">{qtr}</span>'
        )

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
        )

    table_html = header + "".join(rows_html)
    st.markdown(
        f'<div style="max-height:450px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{table_html}</div>',
        unsafe_allow_html=True,
    )


def _render_surprise_chart(ticker: str, df: pd.DataFrame, colors: dict, theme: str):
    """Render EPS surprise bar chart for a specific ticker."""

    if "Actual" not in df.columns or "Estimate" not in df.columns:
        st.caption("Insufficient data for surprise chart.")
        return

    # Clean data
    chart_df = df.dropna(subset=["Actual", "Estimate"]).copy()
    if chart_df.empty:
        st.caption(f"No complete EPS data for {ticker}.")
        return

    # Format period labels
    chart_df["Quarter"] = chart_df["Period"].dt.strftime("%Y Q") + ((chart_df["Period"].dt.month - 1) // 3 + 1).astype(str)

    # Beat/miss stats
    chart_df["Beat"] = chart_df["Actual"] > chart_df["Estimate"]
    beats = chart_df["Beat"].sum()
    total = len(chart_df)
    beat_pct = round(beats / total * 100) if total > 0 else 0

    # KPI
    st.markdown(
        f'<div style="font-size:13px; color:{colors["text_muted"]}; margin:4px 0 12px 0;">'
        f'{ticker} beat EPS estimates <span style="font-weight:700; color:{colors["green"] if beat_pct >= 50 else colors["red"]}">'
        f'{beats} of {total} quarters ({beat_pct}%)</span></div>',
        unsafe_allow_html=True,
    )

    # Melt for grouped bar chart
    melted = chart_df.melt(
        id_vars=["Quarter", "Period"],
        value_vars=["Estimate", "Actual"],
        var_name="Type",
        value_name="EPS",
    )

    bar_colors = {"Estimate": colors["text_muted"], "Actual": "#3D85C6"}

    bars = (
        alt.Chart(melted)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Quarter:N", title=None, sort=alt.SortField("Period")),
            xOffset="Type:N",
            y=alt.Y("EPS:Q", title="EPS ($)"),
            color=alt.Color(
                "Type:N",
                scale=alt.Scale(
                    domain=["Estimate", "Actual"],
                    range=[colors["text_muted"], "#3D85C6"],
                ),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=["Quarter:N", "Type:N", alt.Tooltip("EPS:Q", format="$.2f")],
        )
    )

    # Add surprise % text labels on actual bars
    surprise_data = chart_df[["Quarter", "Period", "Surprise_Pct"]].dropna().copy()
    surprise_data["Label"] = surprise_data["Surprise_Pct"].apply(
        lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%"
    )
    surprise_data["Color"] = surprise_data["Surprise_Pct"].apply(
        lambda x: colors["green"] if x > 0 else colors["red"]
    )

    labels = (
        alt.Chart(surprise_data)
        .mark_text(dy=-8, fontSize=10, fontWeight="bold")
        .encode(
            x=alt.X("Quarter:N", sort=alt.SortField("Period")),
            y=alt.Y("Surprise_Pct:Q"),
            text="Label:N",
            color=alt.condition(
                alt.datum.Surprise_Pct > 0,
                alt.value(colors["green"]),
                alt.value(colors["red"]),
            ),
        )
    )

    chart = (bars + labels).properties(height=280)

    bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
    styled = chart.configure(
        background=bg_color,
    ).configure_axis(
        labelColor=colors["text_muted"],
        titleColor=colors["text_muted"],
        gridColor=f'{colors["text_muted"]}22',
    )
    st.altair_chart(styled, use_container_width=True)

    st.caption(
        "Grouped bars: grey = estimate, blue = actual. Labels show surprise %. "
        "Consistent beats suggest conservative management guidance. Data from Finnhub."
    )


# ---------------------------------------------------------------------------
# Tab 2: Sector P/E & Valuation Dashboard
# ---------------------------------------------------------------------------

def _render_sector_valuations_tab(fmp_key: str | None, colors: dict, theme: str):
    """Sector valuation comparison — P/E bars, valuation table, PEG scatter."""

    st.caption(
        "Compare sector valuations using trailing P/E, forward P/E, PEG ratios, and earnings growth. "
        "Data from yfinance sector ETFs. Cheaper sectors (lower P/E relative to growth) may offer better risk/reward."
    )

    with st.expander("How to Use Sector Valuations"):
        st.markdown(
            "**Trailing P/E** — Price relative to last 12 months' earnings. Lower = cheaper, but could reflect low growth.\n\n"
            "**Forward P/E** — Price relative to next 12 months' estimated earnings. More forward-looking than trailing.\n\n"
            "**PEG Ratio** — P/E divided by earnings growth rate. PEG < 1.0 suggests the stock is cheap relative to its growth. "
            "PEG > 2.0 suggests it may be expensive.\n\n"
            "**PEG Scatter** — Plots Forward P/E vs estimated earnings growth. Sectors below the PEG=1 diagonal line "
            "are growing faster than their valuation implies — potentially undervalued.\n\n"
            "**Dividend Yield** — Annual dividend as % of price. Higher yields in defensive sectors (Utilities, Staples) "
            "often signal value but also lower growth expectations."
        )

    with st.spinner("Fetching sector valuations..."):
        val_df = fetch_sector_valuations()

    if val_df.empty:
        st.warning("Unable to fetch sector valuation data. Click 🔄 to refresh.")
        return

    # ---- Valuation Bar Chart (Forward P/E) ----
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
        f'Sector Forward P/E Comparison</div>',
        unsafe_allow_html=True,
    )

    pe_data = val_df.dropna(subset=["Trailing_PE"]).copy()
    if not pe_data.empty:
        # Market average line
        spy_info = None
        try:
            spy_info = yf.Ticker("SPY").info
        except Exception:
            pass
        spy_fwd_pe = spy_info.get("trailingPE") if spy_info else None

        bars = (
            alt.Chart(pe_data)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                y=alt.Y("Sector:N", sort=alt.SortField("Trailing_PE", order="descending"),
                         title=None, axis=alt.Axis(labelFontSize=11)),
                x=alt.X("Trailing_PE:Q", title="Trailing P/E"),
                color=alt.Color(
                    "Trailing_PE:Q",
                    scale=alt.Scale(scheme="redyellowgreen", reverse=True),
                    legend=None,
                ),
                tooltip=[
                    "Sector:N",
                    alt.Tooltip("Trailing_PE:Q", format=".1f", title="P/E"),
                    alt.Tooltip("Div_Yield:Q", format=".2f", title="Div Yield %"),
                ],
            )
        )

        layers = [bars]

        # SPY average reference line
        if spy_fwd_pe:
            ref_line = (
                alt.Chart(pd.DataFrame({"x": [spy_fwd_pe]}))
                .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["text_muted"])
                .encode(x="x:Q")
            )
            ref_label = (
                alt.Chart(pd.DataFrame({"x": [spy_fwd_pe], "label": [f"SPY {spy_fwd_pe:.1f}"]}))
                .mark_text(align="left", dx=4, dy=-8, fontSize=10, color=colors["text_muted"])
                .encode(x="x:Q", text="label:N")
            )
            layers.extend([ref_line, ref_label])

        chart = layers[0]
        for layer in layers[1:]:
            chart = chart + layer

        bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
        styled = chart.properties(height=320).configure(
            background=bg_color,
        ).configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            gridColor=f'{colors["text_muted"]}22',
        )
        st.altair_chart(styled, use_container_width=True)

    # ---- Valuation Table ----
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 4px 0;">'
        f'Sector Valuation Metrics</div>',
        unsafe_allow_html=True,
    )

    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:0.6">ETF</span>'
        '<span style="flex:1.3">Sector</span>'
        '<span style="flex:0.7;text-align:right">P/E</span>'
        '<span style="flex:0.6;text-align:right">P/B</span>'
        '<span style="flex:0.7;text-align:right">Yield</span>'
        '<span style="flex:0.5;text-align:right">Beta</span>'
        '<span style="flex:0.7;text-align:right">3M</span>'
        '<span style="flex:0.7;text-align:right">YTD</span>'
        '<span style="flex:0.7;text-align:right">1Y</span>'
        '<span style="flex:0.7;text-align:right">3Y Avg</span>'
        '<span style="flex:0.7;text-align:right">5Y Avg</span>'
        '</div>'
    )

    rows_html = []
    for _, row in val_df.iterrows():
        def _fmt(val, fmt=".1f"):
            return f"{val:{fmt}}" if pd.notna(val) else "—"

        def _fmt_pct(val):
            return f"{val:.2f}%" if pd.notna(val) else "—"

        def _fmt_ret(val):
            if pd.isna(val) or val is None:
                return f'<span style="color:{colors["text_muted"]}">—</span>'
            clr = colors["green"] if val > 0 else colors["red"]
            return f'<span style="color:{clr}">{val:+.1f}%</span>'

        cells = (
            f'<span style="flex:0.6;font-weight:600">{row["Ticker"]}</span>'
            f'<span style="flex:1.3">{row["Sector"]}</span>'
            f'<span style="flex:0.7;text-align:right">{_fmt(row.get("Trailing_PE"))}</span>'
            f'<span style="flex:0.6;text-align:right">{_fmt(row.get("P/B"), ".2f")}</span>'
            f'<span style="flex:0.7;text-align:right;color:{colors["green"] if pd.notna(row.get("Div_Yield")) and row["Div_Yield"] > 2 else colors["text"]}">{_fmt_pct(row.get("Div_Yield"))}</span>'
            f'<span style="flex:0.5;text-align:right">{_fmt(row.get("Beta"), ".2f")}</span>'
            f'<span style="flex:0.7;text-align:right">{_fmt_ret(row.get("3M"))}</span>'
            f'<span style="flex:0.7;text-align:right">{_fmt_ret(row.get("YTD"))}</span>'
            f'<span style="flex:0.7;text-align:right">{_fmt_ret(row.get("1Y"))}</span>'
            f'<span style="flex:0.7;text-align:right">{_fmt_ret(row.get("3Y_Avg"))}</span>'
            f'<span style="flex:0.7;text-align:right">{_fmt_ret(row.get("5Y_Avg"))}</span>'
        )

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
        )

    st.markdown(
        f'<div style="border:1px solid {colors["border"]}33; border-radius:6px;">'
        f'{header}{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Data: yfinance (SPDR sector ETFs). P/E = trailing 12-month price-to-earnings. "
        "P/B = price-to-book. Yield = trailing annual dividend yield. "
        "3M/YTD/1Y = period returns, 3Y/5Y = annualized averages. "
        "Note: Forward P/E and PEG ratios not available for ETFs via yfinance."
    )

    # ---- Valuation vs Performance Scatter ----
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Valuation vs Performance</div>',
        unsafe_allow_html=True,
    )

    scatter_df = val_df.dropna(subset=["Trailing_PE", "1Y"]).copy()
    if not scatter_df.empty:
        # SPY reference
        spy_pe = None
        try:
            spy_info = yf.Ticker("SPY").info
            spy_pe = spy_info.get("trailingPE")
        except Exception:
            pass

        points = (
            alt.Chart(scatter_df)
            .mark_circle(size=140)
            .encode(
                x=alt.X("Trailing_PE:Q", title="Trailing P/E", scale=alt.Scale(zero=False)),
                y=alt.Y("1Y:Q", title="1-Year Return (%)"),
                color=alt.condition(
                    alt.datum["1Y"] > 0,
                    alt.value(colors["green"]),
                    alt.value(colors["red"]),
                ),
                tooltip=[
                    "Sector:N",
                    alt.Tooltip("Trailing_PE:Q", format=".1f", title="P/E"),
                    alt.Tooltip("1Y:Q", format="+.1f", title="1Y Return"),
                    alt.Tooltip("Div_Yield:Q", format=".2f", title="Yield %"),
                ],
            )
        )

        labels = (
            alt.Chart(scatter_df)
            .mark_text(dx=8, dy=-8, fontSize=10, color=colors["text_muted"])
            .encode(x="Trailing_PE:Q", y="1Y:Q", text="Sector:N")
        )

        layers = [points, labels]

        # Zero return line
        zero_line = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[6, 3], strokeWidth=1, color=colors["text_muted"], opacity=0.5)
            .encode(y="y:Q")
        )
        layers.append(zero_line)

        # SPY P/E vertical reference
        if spy_pe:
            spy_ref = (
                alt.Chart(pd.DataFrame({"x": [spy_pe]}))
                .mark_rule(strokeDash=[6, 3], strokeWidth=1, color=colors["text_muted"], opacity=0.5)
                .encode(x="x:Q")
            )
            spy_label = (
                alt.Chart(pd.DataFrame({"x": [spy_pe], "label": [f"SPY P/E {spy_pe:.0f}"]}))
                .mark_text(align="left", dx=4, dy=-8, fontSize=10, color=colors["text_muted"])
                .encode(x="x:Q", text="label:N")
            )
            layers.extend([spy_ref, spy_label])

        chart = layers[0]
        for layer in layers[1:]:
            chart = chart + layer

        bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
        styled = chart.properties(height=350).configure(
            background=bg_color,
        ).configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            gridColor=f'{colors["text_muted"]}22',
        )
        st.altair_chart(styled, use_container_width=True)

        st.caption(
            "X-axis = trailing P/E (cheaper → left, expensive → right). "
            "Y-axis = 1-year return. Ideal sectors are in the top-left quadrant "
            "(cheap valuation + strong returns). Vertical dashed = SPY P/E, horizontal = 0% return. "
            "Data from yfinance."
        )
    else:
        st.caption("Insufficient data for valuation scatter.")


def _render_earnings_yf_fallback(colors: dict, theme: str):
    """Fallback: show portfolio earnings from yfinance when no Finnhub key."""
    from components.sidebar import collect_all_tickers

    config = st.session_state.get("config", {})
    all_tickers = collect_all_tickers(config)

    if not all_tickers:
        st.info("No tickers in portfolio. Add strategies/screens/groups in Settings.")
        return

    # Filter to non-index tickers
    stock_tickers = tuple(sorted([t for t in all_tickers if not t.startswith("^")]))

    with st.spinner(f"Checking earnings dates for {len(stock_tickers)} portfolio tickers..."):
        cal_df = fetch_earnings_calendar_yf(stock_tickers)

    if cal_df.empty:
        st.info("No upcoming earnings found for portfolio tickers.")
        return

    # Filter to future dates
    today = pd.Timestamp.today().normalize()
    upcoming = cal_df[cal_df["Date"] >= today].head(30)

    if upcoming.empty:
        st.info("No upcoming earnings found.")
        return

    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Upcoming Portfolio Earnings ({len(upcoming)} reports)</div>',
        unsafe_allow_html=True,
    )

    # Simple table
    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:1.5">Date</span>'
        '<span style="flex:1">Ticker</span>'
        '</div>'
    )

    rows_html = []
    for _, row in upcoming.iterrows():
        d = row["Date"]
        date_str = d.strftime("%b %d, %Y") if pd.notna(d) else "—"
        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">'
            f'<span style="flex:1.5;color:{colors["text_muted"]}">{date_str}</span>'
            f'<span style="flex:1;font-weight:600">{row["Ticker"]}</span>'
            f'</div>'
        )

    table_html = header + "".join(rows_html)
    st.markdown(
        f'<div style="max-height:400px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{table_html}</div>',
        unsafe_allow_html=True,
    )


def _fmt_revenue(val) -> str:
    """Format revenue value to human-readable."""
    if val is None or pd.isna(val):
        return "—"
    val = float(val)
    if abs(val) >= 1e12:
        return f"${val / 1e12:.1f}T"
    elif abs(val) >= 1e9:
        return f"${val / 1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"${val / 1e6:.0f}M"
    elif abs(val) >= 1e3:
        return f"${val / 1e3:.0f}K"
    else:
        return f"${val:.0f}"


# ---------------------------------------------------------------------------
# Tab 3: Insider Transactions
# ---------------------------------------------------------------------------

def _render_insider_tab(finnhub_key: str | None, colors: dict, theme: str):
    """Insider buying/selling feed for selected tickers."""

    st.caption(
        "SEC Form 4 insider transactions — purchases often signal management confidence. "
        "Cluster buying (multiple insiders buying within weeks) is an especially strong signal."
    )

    if not finnhub_key:
        st.warning("Finnhub API key required for insider data. Add it in Settings → API Settings.")
        return

    # Ticker selector from portfolio
    from components.sidebar import collect_all_tickers
    config = st.session_state.get("config", {})
    all_tickers = sorted(collect_all_tickers(config))

    if not all_tickers:
        all_tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

    selected = st.selectbox("Select ticker", all_tickers, index=0, key="insider_ticker")

    with st.spinner(f"Fetching insider transactions for {selected}..."):
        df = fetch_insider_transactions(finnhub_key, selected)
        summary = fetch_insider_summary(finnhub_key, selected)

    if summary:
        # Summary KPIs
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Buys (6M)</div>'
                f'<div style="font-size:24px; font-weight:700; color:{colors["green"]};">{summary["total_buys"]}</div>'
                f'</div>', unsafe_allow_html=True)
        with k2:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Sells (6M)</div>'
                f'<div style="font-size:24px; font-weight:700; color:{colors["red"]};">{summary["total_sells"]}</div>'
                f'</div>', unsafe_allow_html=True)
        with k3:
            bv = summary["buy_value"]
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Buy Value</div>'
                f'<div style="font-size:24px; font-weight:700; color:{colors["green"]};">{_fmt_large_number(bv)}</div>'
                f'</div>', unsafe_allow_html=True)
        with k4:
            nv = summary["net_value"]
            nv_clr = colors["green"] if nv >= 0 else colors["red"]
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Net (Buy-Sell)</div>'
                f'<div style="font-size:24px; font-weight:700; color:{nv_clr};">{_fmt_large_number(nv)}</div>'
                f'</div>', unsafe_allow_html=True)

    if df.empty:
        st.caption(f"No insider transactions found for {selected}.")
        return

    # Transaction table
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
        f'Recent Insider Transactions — {selected}</div>',
        unsafe_allow_html=True,
    )

    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:1">Date</span>'
        '<span style="flex:2">Name</span>'
        '<span style="flex:0.8;text-align:center">Type</span>'
        '<span style="flex:1;text-align:right">Shares</span>'
        '<span style="flex:0.8;text-align:right">Price</span>'
        '<span style="flex:1;text-align:right">Value</span>'
        '<span style="flex:0.8">Source</span>'
        '</div>'
    )

    rows_html = []
    for _, row in df.head(30).iterrows():
        tx_type = row.get("Type", "")
        type_clr = colors["green"] if tx_type == "Purchase" else colors["red"] if tx_type == "Sale" else colors["text_muted"]

        dt_str = row["Date"].strftime("%b %d, %Y") if pd.notna(row.get("Date")) else "—"
        shares = row.get("Shares", 0)
        shares_str = f"{shares:+,.0f}" if shares else "—"
        price = row.get("Price", 0)
        price_str = f"${price:,.2f}" if price and price > 0 else "—"
        value = row.get("Value", 0)
        value_str = _fmt_large_number(value) if value and value > 0 else "—"

        cells = (
            f'<span style="flex:1">{dt_str}</span>'
            f'<span style="flex:2">{row.get("Name", "")}</span>'
            f'<span style="flex:0.8;text-align:center;color:{type_clr};font-weight:600">{tx_type}</span>'
            f'<span style="flex:1;text-align:right">{shares_str}</span>'
            f'<span style="flex:0.8;text-align:right">{price_str}</span>'
            f'<span style="flex:1;text-align:right">{value_str}</span>'
            f'<span style="flex:0.8;font-size:10px;color:{colors["text_muted"]}">{row.get("Source", "")}</span>'
        )

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
        )

    st.markdown(
        f'<div style="max-height:400px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{header}{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Data from Finnhub (SEC Form 4 filings). P = Purchase, S = Sale, M = Option Exercise.")


# ---------------------------------------------------------------------------
# Tab 4: Dividends
# ---------------------------------------------------------------------------

def _render_dividends_tab(colors: dict, theme: str):
    """Dividend scanner for portfolio tickers."""

    st.caption(
        "Dividend yield scanner for your portfolio. Shows current yield, payout ratio, "
        "ex-dividend dates, and payment frequency. High yield + low payout = sustainable dividend."
    )

    # Collect tickers from portfolio
    from components.sidebar import collect_all_tickers
    config = st.session_state.get("config", {})
    all_tickers = sorted(collect_all_tickers(config))

    if not all_tickers:
        all_tickers = ["AAPL", "MSFT", "JNJ", "KO", "PG", "XOM", "T", "VZ"]

    with st.spinner(f"Scanning {len(all_tickers)} tickers for dividends..."):
        div_df = fetch_dividend_data(tuple(all_tickers))

    if div_df.empty:
        st.warning("No dividend-paying stocks found in your portfolio.")
        return

    # KPI summary
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Dividend Payers</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["green"]};">{len(div_df)}</div>'
            f'</div>', unsafe_allow_html=True)
    with k2:
        avg_yield = div_df["Div_Yield"].mean()
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Avg Yield</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["green"]};">{avg_yield:.2f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k3:
        max_row = div_df.iloc[0]
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Highest Yield</div>'
            f'<div style="font-size:20px; font-weight:700; color:{colors["green"]};">'
            f'{max_row["Ticker"]} {max_row["Div_Yield"]:.2f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k4:
        payout_safe = div_df.dropna(subset=["Payout"])
        safe_count = len(payout_safe[payout_safe["Payout"] < 60]) if not payout_safe.empty else 0
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Safe Payout (&lt;60%)</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["green"]};">{safe_count}</div>'
            f'</div>', unsafe_allow_html=True)

    # Dividend table
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
        f'Dividend Scanner ({len(div_df)} stocks)</div>',
        unsafe_allow_html=True,
    )

    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:0.7">Ticker</span>'
        '<span style="flex:2">Name</span>'
        '<span style="flex:0.8;text-align:right">Yield</span>'
        '<span style="flex:0.7;text-align:right">Rate</span>'
        '<span style="flex:0.8;text-align:right">Payout</span>'
        '<span style="flex:0.7;text-align:center">Freq</span>'
        '<span style="flex:1.2">Ex-Date</span>'
        '<span style="flex:0.6">Source</span>'
        '</div>'
    )

    rows_html = []
    for _, row in div_df.iterrows():
        yld = row.get("Div_Yield", 0)
        yld_clr = colors["green"] if yld >= 3 else colors["text"] if yld >= 1 else colors["text_muted"]

        payout = row.get("Payout")
        if pd.notna(payout):
            p_clr = colors["green"] if payout < 60 else colors["red"] if payout > 90 else "#E8A838"
            p_str = f"{payout:.0f}%"
        else:
            p_clr = colors["text_muted"]
            p_str = "—"

        rate = row.get("Div_Rate")
        rate_str = f"${rate:.2f}" if pd.notna(rate) else "—"

        name = row.get("Name", "")
        if len(name) > 22:
            name = name[:20] + "..."

        cells = (
            f'<span style="flex:0.7;font-weight:600">{row["Ticker"]}</span>'
            f'<span style="flex:2;font-size:11px">{name}</span>'
            f'<span style="flex:0.8;text-align:right;color:{yld_clr};font-weight:600">{yld:.2f}%</span>'
            f'<span style="flex:0.7;text-align:right">{rate_str}</span>'
            f'<span style="flex:0.8;text-align:right;color:{p_clr}">{p_str}</span>'
            f'<span style="flex:0.7;text-align:center;font-size:10px">{row.get("Frequency", "—")}</span>'
            f'<span style="flex:1.2;font-size:11px">{row.get("Ex_Date", "—")}</span>'
            f'<span style="flex:0.6;font-size:10px;color:{colors["text_muted"]}">{row.get("Source", "")}</span>'
        )

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
        )

    st.markdown(
        f'<div style="max-height:400px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{header}{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Data from yfinance. Yield = trailing annual dividend yield. "
        "Payout = dividend as % of earnings (< 60% = sustainable, > 90% = at risk). "
        "Sorted by yield descending."
    )


# ---------------------------------------------------------------------------
# Tab 5: Analyst Revisions
# ---------------------------------------------------------------------------

def _render_analyst_tab(finnhub_key: str | None, colors: dict, theme: str):
    """Analyst recommendations, upgrades/downgrades, and price targets."""

    st.caption(
        "Analyst consensus, recent rating changes, and price targets. "
        "Track revision momentum — upgrades clustering often precede price moves."
    )

    if not finnhub_key:
        st.warning("Finnhub API key required for analyst data. Add it in Settings → API Settings.")
        return

    from components.sidebar import collect_all_tickers
    config = st.session_state.get("config", {})
    all_tickers = sorted(collect_all_tickers(config))

    if not all_tickers:
        all_tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

    selected = st.selectbox("Select ticker", all_tickers, index=0, key="analyst_ticker")

    # Fetch all data
    with st.spinner(f"Fetching analyst data for {selected}..."):
        recs = fetch_analyst_recommendations(finnhub_key, selected)
        upgrades = fetch_analyst_upgrades(finnhub_key, selected)
        targets = fetch_price_target(finnhub_key, selected)

    # ---- Price Target ----
    if targets and targets.get("targetMean"):
        current = targets.get("lastUpdated", "")
        t_high = targets.get("targetHigh", 0)
        t_low = targets.get("targetLow", 0)
        t_mean = targets.get("targetMean", 0)
        t_median = targets.get("targetMedian", 0)

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Target Low</div>'
                f'<div style="font-size:22px; font-weight:700; color:{colors["red"]};">${t_low:,.0f}</div>'
                f'</div>', unsafe_allow_html=True)
        with k2:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Target Mean</div>'
                f'<div style="font-size:22px; font-weight:700; color:{colors["text"]};">${t_mean:,.0f}</div>'
                f'</div>', unsafe_allow_html=True)
        with k3:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Target High</div>'
                f'<div style="font-size:22px; font-weight:700; color:{colors["green"]};">${t_high:,.0f}</div>'
                f'</div>', unsafe_allow_html=True)
        with k4:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Median</div>'
                f'<div style="font-size:22px; font-weight:700; color:{colors["text"]};">${t_median:,.0f}</div>'
                f'</div>', unsafe_allow_html=True)

    # ---- Recommendation Trend Chart ----
    if not recs.empty:
        st.markdown(
            f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 4px 0;">'
            f'Analyst Recommendation Trend — {selected}</div>',
            unsafe_allow_html=True,
        )

        rec_melted = recs.melt(
            id_vars=["period"], value_vars=["strongBuy", "buy", "hold", "sell", "strongSell"],
            var_name="Rating", value_name="Count",
        )

        rating_colors = {
            "strongBuy": "#2E7D32", "buy": "#6AA84F",
            "hold": "#E8A838", "sell": "#E06666", "strongSell": "#B71C1C",
        }
        rating_order = ["strongSell", "sell", "hold", "buy", "strongBuy"]

        rec_chart = (
            alt.Chart(rec_melted)
            .mark_bar()
            .encode(
                x=alt.X("period:T", title=None, axis=alt.Axis(format="%b %Y")),
                y=alt.Y("Count:Q", title="Number of Analysts", stack=True),
                color=alt.Color(
                    "Rating:N",
                    scale=alt.Scale(domain=rating_order, range=[rating_colors[r] for r in rating_order]),
                    legend=alt.Legend(orient="top", title=None),
                ),
                order=alt.Order("order:Q"),
                tooltip=["Rating:N", "Count:Q", alt.Tooltip("period:T", format="%b %Y")],
            )
        )

        # Add order for stacking
        order_map = {r: i for i, r in enumerate(rating_order)}
        rec_melted["order"] = rec_melted["Rating"].map(order_map)

        bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
        styled = rec_chart.properties(height=250).configure(
            background=bg_color,
        ).configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            gridColor=f'{colors["text_muted"]}22',
        )
        st.altair_chart(styled, use_container_width=True)

    # ---- Recent Upgrades/Downgrades ----
    if not upgrades.empty:
        st.markdown(
            f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
            f'Recent Rating Changes — {selected}</div>',
            unsafe_allow_html=True,
        )

        header = (
            '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
            f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
            '<span style="flex:1">Date</span>'
            '<span style="flex:2">Firm</span>'
            '<span style="flex:1;text-align:center">Action</span>'
            '<span style="flex:1.2;text-align:right">From</span>'
            '<span style="flex:0.3;text-align:center">→</span>'
            '<span style="flex:1.2">To</span>'
            '<span style="flex:0.6">Source</span>'
            '</div>'
        )

        rows_html = []
        for _, row in upgrades.head(20).iterrows():
            dt_str = row["Date"].strftime("%b %d, %Y") if pd.notna(row.get("Date")) else "—"
            action = row.get("Action", "")
            action_clr = colors["green"] if "upgrade" in action.lower() else colors["red"] if "downgrade" in action.lower() else colors["text"]

            cells = (
                f'<span style="flex:1">{dt_str}</span>'
                f'<span style="flex:2">{row.get("Firm", "")}</span>'
                f'<span style="flex:1;text-align:center;color:{action_clr};font-weight:600">{action}</span>'
                f'<span style="flex:1.2;text-align:right">{row.get("From", "—")}</span>'
                f'<span style="flex:0.3;text-align:center;color:{colors["text_muted"]}">→</span>'
                f'<span style="flex:1.2">{row.get("To", "—")}</span>'
                f'<span style="flex:0.6;font-size:10px;color:{colors["text_muted"]}">{row.get("Source", "")}</span>'
            )

            rows_html.append(
                f'<div style="display:flex; padding:3px 8px; font-size:12px; '
                f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
            )

        st.markdown(
            f'<div style="max-height:350px; overflow-y:auto; border:1px solid {colors["border"]}33; '
            f'border-radius:6px;">{header}{"".join(rows_html)}</div>',
            unsafe_allow_html=True,
        )

    if recs.empty and upgrades.empty and not targets:
        st.caption(f"No analyst data found for {selected}.")

    st.caption("Data from Finnhub. Analyst recommendations and price targets from major Wall Street firms.")


# ---------------------------------------------------------------------------
# Tab 6: IPO Calendar
# ---------------------------------------------------------------------------

def _render_ipo_tab(finnhub_key: str | None, colors: dict, theme: str):
    """Upcoming IPOs with details."""

    st.caption(
        "Upcoming IPO filings and pricing. Track new listings, offering sizes, and exchanges. "
        "Large IPOs can affect sector performance and market liquidity."
    )

    if not finnhub_key:
        st.warning("Finnhub API key required for IPO data. Add it in Settings → API Settings.")
        return

    # Date range
    today = date.today()
    start = today.isoformat()
    end = (today + timedelta(days=90)).isoformat()

    with st.spinner("Fetching IPO calendar..."):
        ipo_df = fetch_ipo_calendar(finnhub_key, start, end)

    if ipo_df.empty:
        st.caption("No upcoming IPOs found.")
        return

    # Summary
    expected = len(ipo_df[ipo_df["Status"] == "expected"])
    filed = len(ipo_df[ipo_df["Status"] == "filed"])
    priced = len(ipo_df[ipo_df["Status"] == "priced"])
    total_value = ipo_df["Value"].sum()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Total IPOs</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["text"]};">{len(ipo_df)}</div>'
            f'</div>', unsafe_allow_html=True)
    with k2:
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Expected</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["green"]};">{expected}</div>'
            f'</div>', unsafe_allow_html=True)
    with k3:
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Filed</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["text_muted"]};">{filed}</div>'
            f'</div>', unsafe_allow_html=True)
    with k4:
        st.markdown(
            f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]};">Total Value</div>'
            f'<div style="font-size:24px; font-weight:700; color:{colors["text"]};">{_fmt_large_number(total_value)}</div>'
            f'</div>', unsafe_allow_html=True)

    # IPO Table
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
        f'Upcoming IPOs (next 90 days)</div>',
        unsafe_allow_html=True,
    )

    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:0.8">Date</span>'
        '<span style="flex:0.6">Symbol</span>'
        '<span style="flex:2.5">Company</span>'
        '<span style="flex:1.2">Exchange</span>'
        '<span style="flex:0.9;text-align:right">Price</span>'
        '<span style="flex:0.8;text-align:right">Shares</span>'
        '<span style="flex:0.8;text-align:right">Value</span>'
        '<span style="flex:0.6;text-align:center">Status</span>'
        '<span style="flex:0.5">Source</span>'
        '</div>'
    )

    rows_html = []
    for _, row in ipo_df.iterrows():
        dt_str = row["Date"].strftime("%b %d") if pd.notna(row.get("Date")) else "—"
        status = row.get("Status", "")
        status_clr = colors["green"] if status == "expected" else colors["text_muted"]

        shares = row.get("Shares", 0)
        shares_str = f"{shares / 1e6:.1f}M" if shares and shares >= 1e6 else f"{shares:,.0f}" if shares else "—"
        value = row.get("Value", 0)
        value_str = _fmt_large_number(value) if value and value > 0 else "—"

        company = row.get("Company", "")
        if len(company) > 30:
            company = company[:28] + "..."

        cells = (
            f'<span style="flex:0.8">{dt_str}</span>'
            f'<span style="flex:0.6;font-weight:600">{row.get("Symbol", "")}</span>'
            f'<span style="flex:2.5;font-size:11px">{company}</span>'
            f'<span style="flex:1.2;font-size:10px">{row.get("Exchange", "")}</span>'
            f'<span style="flex:0.9;text-align:right;font-size:11px">{row.get("Price Range", "—")}</span>'
            f'<span style="flex:0.8;text-align:right">{shares_str}</span>'
            f'<span style="flex:0.8;text-align:right">{value_str}</span>'
            f'<span style="flex:0.6;text-align:center;color:{status_clr};font-size:10px">{status}</span>'
            f'<span style="flex:0.5;font-size:10px;color:{colors["text_muted"]}">{row.get("Source", "")}</span>'
        )

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
        )

    st.markdown(
        f'<div style="max-height:500px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{header}{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Data from Finnhub. IPO dates and terms are subject to change. Status: expected = scheduled, filed = SEC filing submitted.")
