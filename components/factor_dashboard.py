"""Dynamic Factor Regime Dashboard — full-page view with regime cards, z-score charts, stats, and backtest."""

import altair as alt
import pandas as pd
import streamlit as st

from services.factor_data import (
    FACTOR_COLORS,
    FACTOR_ETFS,
    fetch_factor_regime_data,
)


def render_factor_dashboard(colors: dict, theme: str):
    """Render the full factor regime dashboard, replacing the normal main content."""

    # Header
    st.markdown(
        f"""
        <div style="text-align:center; padding: 10px 0 4px 0;">
            <div style="font-size:28px; font-weight:700; color:{colors['text_header']};">
                Dynamic Factor Regime Dashboard
            </div>
            <div style="font-size:13px; color:{colors['text_muted']};">
                Momentum-based regime switching across equity factor ETFs
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Halflife slider — shared across all tabs
    halflife = st.slider(
        "EWMA Halflife (days)", min_value=30, max_value=180, value=90, step=10,
        help="Controls trend sensitivity. Lower = more responsive, higher = smoother.",
    )

    data = fetch_factor_regime_data(halflife)
    if not data:
        st.warning("Unable to fetch factor data. Please try again later.")
        return

    # Tabs
    tab_dash, tab_regime, tab_stats, tab_bt = st.tabs(
        ["Dashboard", "Regime Charts", "Statistics", "Backtest"]
    )

    with tab_dash:
        _render_dashboard_tab(data, colors, theme)

    with tab_regime:
        _render_regime_charts_tab(data, colors, theme)

    with tab_stats:
        _render_statistics_tab(data, colors, theme)

    with tab_bt:
        _render_backtest_tab(data, colors, theme)


def _render_dashboard_tab(data: dict, colors: dict, theme: str):
    """Main dashboard: regime cards, z-score chart, methodology."""

    regimes = data["regimes"]
    zscore_df = data["zscore_df"]

    # Factor cards
    cols = st.columns(len(FACTOR_ETFS))
    for i, (name, etf) in enumerate(FACTOR_ETFS.items()):
        info = regimes.get(name, {})
        regime = info.get("regime", "N/A")
        zscore = info.get("zscore", 0)
        days = info.get("days_in_regime", 0)

        regime_color = colors["green"] if regime == "BULL" else colors["red"]
        regime_bg = f"{regime_color}18"

        with cols[i]:
            st.markdown(
                f"""
                <div class="factor-card">
                    <div style="font-size:11px; color:{colors['text_muted']}; text-transform:uppercase; letter-spacing:1px;">
                        {name} ({etf})
                    </div>
                    <div style="font-size:28px; font-weight:800; color:{regime_color}; margin:6px 0;">
                        {regime}
                    </div>
                    <div style="font-size:12px; color:{colors['text_muted']};">
                        Z-Score: {zscore:.2f}
                    </div>
                    <div style="font-size:11px; color:{colors['text_muted']};">
                        {days} days in regime
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Z-score line chart
    st.markdown(
        f"""<div class="factor-card" style="margin-top:16px; padding:16px 20px 8px 20px;">
            <div style="font-size:16px; font-weight:600; color:{colors['text_header']}; margin-bottom:8px;">
                Smoothed Z-Scores Over Time
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    _render_zscore_chart(zscore_df, colors, theme)

    # Volume Conviction panel
    volume_conviction = data.get("volume_conviction", {})
    if volume_conviction:
        _render_volume_conviction(volume_conviction, regimes, colors, theme)

    # Relative volume trend chart
    rel_vol_df = data.get("rel_vol_df")
    if rel_vol_df is not None and not rel_vol_df.empty:
        _render_rel_vol_chart(rel_vol_df, colors, theme)

    # Methodology
    with st.expander("Methodology", expanded=False):
        st.markdown(
            f"""
            <div style="color:{colors['text']}; font-size:13px; line-height:1.7;">
                <p style="font-style:italic; color:{colors['text_muted']};">
                    This dashboard is inspired by the factor investing research of
                    <b>AQR Capital Management</b>, particularly:
                    Asness, Moskowitz &amp; Pedersen — <i>"Value and Momentum Everywhere"</i> (2013, Journal of Finance);
                    Gupta &amp; Kelly — <i>"Factor Momentum Everywhere"</i> (2019, Journal of Portfolio Management);
                    and AQR's <i>"A Century of Evidence on Trend-Following"</i>.
                    The EWMA z-score regime framework, factor taxonomy (Value, Size, Momentum, Quality, Growth),
                    and expanding-window normalization are adapted from these works.
                </p>
                <hr style="border-color:{colors['border']}44; margin:12px 0;">
                <p><b>Regime Detection</b></p>
                <p><b>1. Active Returns:</b> Daily factor ETF return minus S&P 500 return (beta=1 assumption).</p>
                <p><b>2. Trend Estimation:</b> EWMA of daily active returns (configurable halflife).</p>
                <p><b>3. Z-Score Normalization:</b> Expanding-window z-score of the EWMA trend, measuring deviation from historical mean.</p>
                <p><b>4. Smoothing:</b> Second EWMA applied to z-scores to reduce whipsaws.</p>
                <p><b>5. Regime Classification:</b> Smoothed z-score &ge; 0 &rarr;
                    <span style="color:{colors['green']}; font-weight:700;">BULL</span>,
                    &lt; 0 &rarr;
                    <span style="color:{colors['red']}; font-weight:700;">BEAR</span>.
                </p>
                <hr style="border-color:{colors['border']}44; margin:12px 0;">
                <p><b>Volume Conviction</b> — based on Lee &amp; Swaminathan (2000, <i>Journal of Finance</i>)
                    and Blume, Easley &amp; O'Hara (1994). Thresholds are percentile-based on each ETF's own volume history.</p>
                <p><b>During a regime shift</b> (first 30 days):</p>
                <ul>
                    <li><span style="color:{colors['green']}; font-weight:600;">High</span> — Volume below 25th percentile.
                        Research shows low-volume momentum shifts are more persistent and durable.</li>
                    <li><span style="color:{colors['text_muted']};">Neutral</span> — Normal volume range. No strong signal either way.</li>
                    <li><span style="color:#E8A838; font-weight:600;">Elevated</span> — Volume above 75th percentile.
                        Above-average activity — monitor for potential reversal.</li>
                    <li><span style="color:{colors['red']}; font-weight:600;">Caution</span> — Volume above 90th percentile.
                        High-volume shifts historically overreact and reverse faster.</li>
                </ul>
                <p><b>During an established regime</b> (after 30 days):</p>
                <ul>
                    <li><span style="color:#6FA8DC; font-weight:600;">Quiet</span> — Volume below 25th percentile. Low activity, regime stable.</li>
                    <li><span style="color:{colors['text_muted']};">Steady</span> — Normal volume. Regime continuing as expected.</li>
                    <li><span style="color:#E8A838; font-weight:600;">Active</span> — Volume above 75th percentile. Increased institutional activity.</li>
                    <li><span style="color:{colors['red']}; font-weight:600;">Watch</span> — Volume above 90th percentile.
                        Unusual activity may signal a coming regime change.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_volume_conviction(volume_conviction: dict, regimes: dict,
                               colors: dict, theme: str):
    """Render volume conviction cards for each factor ETF."""

    st.markdown(
        f"""<div class="factor-card" style="margin-top:16px; padding:16px 20px 8px 20px;">
            <div style="font-size:16px; font-weight:600; color:{colors['text_header']}; margin-bottom:4px;">
                Volume Conviction
            </div>
            <div style="font-size:11px; color:{colors['text_muted']}; margin-bottom:12px;">
                Based on Lee &amp; Swaminathan (2000): low-volume regime shifts tend to be more persistent,
                while high-volume shifts often signal overreaction that reverses.
                Blume, Easley &amp; O'Hara (1994) showed volume reveals information quality beyond price alone.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    cols = st.columns(len(volume_conviction))
    for i, (name, vc) in enumerate(volume_conviction.items()):
        regime_info = regimes.get(name, {})
        regime = regime_info.get("regime", "N/A")

        conviction = vc["conviction"]
        rel_vol = vc["rel_volume"]
        rel_vol_5d = vc["rel_volume_5d"]
        vol_z = vc["vol_zscore"]
        note = vc["conviction_note"]

        # Conviction badge color
        _CONVICTION_COLORS = {
            "High":     (colors["green"],  f"{colors['green']}20"),   # Low-vol shift, strong signal
            "Caution":  (colors["red"],    f"{colors['red']}20"),     # High-vol shift, overreaction risk
            "Elevated": ("#E8A838",        "#E8A83820"),              # Above-avg vol during shift
            "Watch":    (colors["red"],    f"{colors['red']}20"),     # Unusual vol, regime may change
            "Active":   ("#E8A838",        "#E8A83820"),              # Above-avg vol, established
            "Quiet":    ("#6FA8DC",        "#6FA8DC20"),              # Low vol, stable
            "Neutral":  (colors["text_muted"], f"{colors['text_muted']}15"),
            "Steady":   (colors["text_muted"], f"{colors['text_muted']}15"),
        }
        badge_color, badge_bg = _CONVICTION_COLORS.get(
            conviction, (colors["text_muted"], f"{colors['text_muted']}15"))

        # Relative volume bar color
        if rel_vol > 1.5:
            rv_color = "#E8A838"  # amber — elevated
        elif rel_vol > 2.0:
            rv_color = colors["red"]  # high
        elif rel_vol < 0.7:
            rv_color = "#6FA8DC"  # blue — low
        else:
            rv_color = colors["text_muted"]

        # Format volume
        curr_vol = vc["current_volume"]
        if curr_vol >= 1_000_000:
            vol_str = f"{curr_vol / 1_000_000:.1f}M"
        elif curr_vol >= 1_000:
            vol_str = f"{curr_vol / 1_000:.0f}K"
        else:
            vol_str = str(curr_vol)

        with cols[i]:
            st.markdown(
                f"""
                <div class="factor-card" style="text-align:center; padding:10px 6px;">
                    <div style="font-size:10px; color:{colors['text_muted']}; text-transform:uppercase; letter-spacing:0.5px;">
                        {name} ({vc['etf']})
                    </div>
                    <div style="display:inline-block; padding:3px 10px; border-radius:12px; margin:6px 0;
                                background:{badge_bg}; border:1px solid {badge_color}44;">
                        <span style="font-size:13px; font-weight:700; color:{badge_color};">{conviction}</span>
                    </div>
                    <div style="font-size:20px; font-weight:700; color:{rv_color}; margin:4px 0;">
                        {rel_vol:.2f}x
                    </div>
                    <div style="font-size:10px; color:{colors['text_muted']};">Prev. Day Rel. Volume</div>
                    <div style="display:flex; justify-content:space-around; margin:8px 0 4px 0; font-size:11px;">
                        <div>
                            <div style="color:{colors['text_muted']};">5D Avg</div>
                            <div style="font-weight:600; color:{colors['text']};">{rel_vol_5d:.2f}x</div>
                        </div>
                        <div>
                            <div style="color:{colors['text_muted']};">Vol Z</div>
                            <div style="font-weight:600; color:{colors['text']};">{vol_z:+.1f}</div>
                        </div>
                        <div>
                            <div style="color:{colors['text_muted']};">Volume</div>
                            <div style="font-weight:600; color:{colors['text']};">{vol_str}</div>
                        </div>
                    </div>
                    <div style="font-size:9px; color:{colors['text_muted']}; margin-top:6px; font-style:italic;">
                        {note}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_rel_vol_chart(rel_vol_df: pd.DataFrame, colors: dict, theme: str):
    """Render smoothed relative volume trend chart for all factors."""

    st.markdown(
        f"""<div class="factor-card" style="margin-top:16px; padding:16px 20px 8px 20px;">
            <div style="font-size:16px; font-weight:600; color:{colors['text_header']}; margin-bottom:4px;">
                Relative Volume Trend
            </div>
            <div style="font-size:11px; color:{colors['text_muted']}; margin-bottom:8px;">
                Smoothed 20-day rolling volume relative to 60-day average.
                Values above 1.0 = above-average activity, below 1.0 = quiet.
                Spikes often coincide with regime transitions.
                Inspired by Blume, Easley &amp; O'Hara (1994, <i>Journal of Finance</i>) who showed volume reveals
                information quality beyond price alone, and Lee &amp; Swaminathan (2000, <i>Journal of Finance</i>)
                who demonstrated that trading volume predicts the magnitude and persistence of momentum.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    df = rel_vol_df.copy()
    df.index.name = "Date"
    df = df.reset_index()

    melted = df.melt(id_vars="Date", var_name="Factor", value_name="RelVol")
    melted = melted.dropna(subset=["RelVol"])

    # Use percentiles for y-axis bounds only (no data clipping)
    p05 = float(melted["RelVol"].quantile(0.05))
    p95 = float(melted["RelVol"].quantile(0.95))

    color_domain = list(FACTOR_COLORS.keys())
    color_range = [FACTOR_COLORS[f] for f in color_domain]

    lines = (
        alt.Chart(melted)
        .mark_line(strokeWidth=1.5, clip=True)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
            y=alt.Y("RelVol:Q", title="Relative Volume",
                     scale=alt.Scale(domain=[p05 * 0.9, p95 * 1.1])),
            color=alt.Color(
                "Factor:N",
                scale=alt.Scale(domain=color_domain, range=color_range),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=["Factor:N", alt.Tooltip("RelVol:Q", format=".2f"), "Date:T"],
        )
    )

    # 1.0x reference line
    ref_line = (
        alt.Chart(pd.DataFrame({"y": [1.0]}))
        .mark_rule(strokeDash=[6, 3], strokeWidth=1.5, color=colors["text_muted"])
        .encode(y="y:Q")
    )

    chart = (
        (ref_line + lines)
        .properties(height=220)
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

    st.altair_chart(chart, width="stretch")


def _render_zscore_chart(zscore_df: pd.DataFrame, colors: dict, theme: str):
    """Render the main multi-factor z-score Altair line chart."""

    df = zscore_df.copy()
    df.index.name = "Date"
    df = df.reset_index()

    # Melt to long format
    melted = df.melt(id_vars="Date", var_name="Factor", value_name="Z-Score")
    melted = melted.dropna(subset=["Z-Score"])

    color_domain = list(FACTOR_COLORS.keys())
    color_range = [FACTOR_COLORS[f] for f in color_domain]

    # Lines
    lines = (
        alt.Chart(melted)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y-%m")),
            y=alt.Y("Z-Score:Q", title="Z-Score"),
            color=alt.Color(
                "Factor:N",
                scale=alt.Scale(domain=color_domain, range=color_range),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=["Factor:N", alt.Tooltip("Z-Score:Q", format=".2f"), "Date:T"],
        )
    )

    # Zero line
    zero_line = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["text_muted"])
        .encode(y="y:Q")
    )

    bg_color = colors["bg_card"]
    text_color = colors["text_muted"]

    chart = (
        (zero_line + lines)
        .properties(height=380)
        .configure_view(strokeWidth=0)
        .configure(background=bg_color)
        .configure_axis(
            labelColor=text_color,
            titleColor=text_color,
            gridColor=f"{colors['border']}80",
            domainColor=colors["border"],
        )
        .configure_legend(
            labelColor=colors["text"],
            titleColor=colors["text"],
        )
    )

    st.altair_chart(chart, width="stretch")


def _render_regime_charts_tab(data: dict, colors: dict, theme: str):
    """Individual per-factor z-score charts with regime shading."""

    zscore_df = data["zscore_df"]

    for name in FACTOR_ETFS:
        if name not in zscore_df.columns:
            continue

        col_data = zscore_df[[name]].dropna().copy()
        col_data.index.name = "Date"
        col_data = col_data.reset_index()
        col_data["Regime"] = col_data[name].apply(lambda z: "BULL" if z >= 0 else "BEAR")

        st.markdown(
            f"""<div style="font-size:15px; font-weight:600; color:{colors['text_header']}; margin:16px 0 4px 0;">
                {name} ({FACTOR_ETFS[name]})
            </div>""",
            unsafe_allow_html=True,
        )

        # Area chart with regime coloring
        area = (
            alt.Chart(col_data)
            .mark_area(opacity=0.3)
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y-%m")),
                y=alt.Y(f"{name}:Q", title="Z-Score"),
                color=alt.Color(
                    "Regime:N",
                    scale=alt.Scale(
                        domain=["BULL", "BEAR"],
                        range=[colors["green"], colors["red"]],
                    ),
                    legend=None,
                ),
            )
        )

        line = (
            alt.Chart(col_data)
            .mark_line(strokeWidth=2, color=FACTOR_COLORS[name])
            .encode(
                x=alt.X("Date:T", axis=alt.Axis(format="%Y-%m")),
                y=f"{name}:Q",
                tooltip=[alt.Tooltip(f"{name}:Q", format=".2f", title="Z-Score"), "Date:T"],
            )
        )

        zero = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["text_muted"])
            .encode(y="y:Q")
        )

        chart = (
            (area + zero + line)
            .properties(height=200)
            .configure_view(strokeWidth=0)
            .configure(background=colors["bg_card"])
            .configure_axis(
                labelColor=colors["text_muted"],
                titleColor=colors["text_muted"],
                gridColor=f"{colors['border']}80",
                domainColor=colors["border"],
            )
        )

        st.altair_chart(chart, width="stretch")


def _render_statistics_tab(data: dict, colors: dict, theme: str):
    """Summary statistics and correlation matrix."""

    stats = data.get("stats", {})
    zscore_df = data["zscore_df"]

    if stats:
        st.markdown(
            f"""<div style="font-size:16px; font-weight:600; color:{colors['text_header']}; margin-bottom:8px;">
                Factor Regime Statistics
            </div>""",
            unsafe_allow_html=True,
        )

        rows = []
        for name, s in stats.items():
            rows.append({
                "Factor": f"{name} ({FACTOR_ETFS[name]})",
                "Bull Days": s["bull_days"],
                "Bear Days": s["bear_days"],
                "Regime Changes": s["regime_changes"],
                "Avg Regime (days)": s["avg_regime_days"],
                "Current Z": s["current_zscore"],
                "Min Z": s["min_zscore"],
                "Max Z": s["max_zscore"],
            })

        st.dataframe(pd.DataFrame(rows).set_index("Factor"), width="stretch")

    # Correlation matrix
    if not zscore_df.empty:
        st.markdown(
            f"""<div style="font-size:16px; font-weight:600; color:{colors['text_header']}; margin:20px 0 8px 0;">
                Z-Score Correlation Matrix
            </div>""",
            unsafe_allow_html=True,
        )
        corr = zscore_df.corr().round(2)
        st.dataframe(corr, width="stretch")


def _render_backtest_tab(data: dict, colors: dict, theme: str):
    """Cumulative active returns chart."""

    cumulative = data.get("cumulative_active_df")
    if cumulative is None or cumulative.empty:
        st.warning("No backtest data available.")
        return

    st.markdown(
        f"""<div style="font-size:16px; font-weight:600; color:{colors['text_header']}; margin-bottom:8px;">
            Cumulative Active Returns vs S&P 500
        </div>
        <div style="font-size:12px; color:{colors['text_muted']}; margin-bottom:12px;">
            Shows the cumulative excess return of each factor ETF over SPY (beta=1 assumption).
        </div>""",
        unsafe_allow_html=True,
    )

    # Date range selector
    min_date = cumulative.index.min().date()
    max_date = cumulative.index.max().date()
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start date", value=min_date, min_value=min_date, max_value=max_date, key="bt_start")
    with c2:
        end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date, key="bt_end")

    # Recompute cumulative from active returns over selected range
    active = data.get("active_returns_df")
    if active is None or active.empty:
        st.warning("No data available.")
        return
    active_slice = active.loc[str(start_date):str(end_date)]
    if active_slice.empty:
        st.warning("No data in selected date range.")
        return
    df = (1 + active_slice).cumprod() - 1

    # Only keep factor columns that exist
    valid_cols = [name for name in FACTOR_ETFS if name in df.columns]
    df = df[valid_cols].dropna(how="all")
    df.index.name = "Date"
    df = df.reset_index()

    melted = df.melt(id_vars="Date", var_name="Factor", value_name="Cumulative Return")
    melted = melted.dropna(subset=["Cumulative Return"])

    color_domain = [f for f in FACTOR_COLORS if f in valid_cols]
    color_range = [FACTOR_COLORS[f] for f in color_domain]

    lines = (
        alt.Chart(melted)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y-%m")),
            y=alt.Y("Cumulative Return:Q", title="Cumulative Active Return", axis=alt.Axis(format=".0%")),
            color=alt.Color(
                "Factor:N",
                scale=alt.Scale(domain=color_domain, range=color_range),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=[
                "Factor:N",
                alt.Tooltip("Cumulative Return:Q", format=".2%"),
                "Date:T",
            ],
        )
    )

    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["text_muted"])
        .encode(y="y:Q")
    )

    chart = (
        (zero + lines)
        .properties(height=400)
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

    st.altair_chart(chart, width="stretch")
