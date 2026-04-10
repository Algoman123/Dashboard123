"""Technicals Dashboard — Sector Rotation, Correlation, AC Regime, RS Ranking, Stage Analysis."""

import altair as alt
import pandas as pd
import streamlit as st

from services.technicals_data import (
    SECTOR_ETFS,
    CORR_ASSETS,
    AC_REGIME_ASSETS,
    AC_LAGS,
    STAGE_LABELS,
    STAGE_COLORS,
    _fetch_rrg_weekly_prices,
    fetch_rrg_data,
    fetch_rrg_backtest_data,
    fetch_correlation_matrix,
    fetch_pair_correlation,
    fetch_ac_regime_data,
    fetch_rs_ranking,
    fetch_stage_analysis,
)


def render_technicals_dashboard(colors: dict, theme: str):
    """Render the full technicals dashboard."""

    # Header with refresh
    hdr_left, hdr_center, hdr_right = st.columns([1, 6, 1])
    with hdr_center:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 10px 0 4px 0;">
                <div style="font-size:28px; font-weight:700; color:{colors['text_header']};">
                    Technicals
                </div>
                <div style="font-size:13px; color:{colors['text_muted']};">
                    Sector rotation, intermarket correlations, regime detection &amp; relative strength
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_right:
        if st.button("🔄", key="refresh_technicals", help="Refresh technicals data"):
            _fetch_rrg_weekly_prices.clear()
            fetch_rrg_backtest_data.clear()
            fetch_correlation_matrix.clear()
            st.rerun()

    tab_rrg, tab_corr, tab_ac, tab_rs, tab_stage = st.tabs([
        "Sector Rotation", "Correlation Matrix", "AC Regime Map",
        "Relative Strength", "Stage Analysis",
    ])

    with tab_rrg:
        _render_rrg_tab(colors, theme)

    with tab_corr:
        _render_correlation_tab(colors, theme)

    with tab_ac:
        _render_ac_regime_tab(colors, theme)

    with tab_rs:
        _render_relative_strength_tab(colors, theme)

    with tab_stage:
        _render_stage_analysis_tab(colors, theme)


def _render_corr_backtest(returns: pd.DataFrame, colors: dict, theme: str):
    """Backtest correlation-based regime switching strategies."""
    import numpy as np

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Correlation Regime Backtester</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Strategy Descriptions", expanded=False):
        st.markdown(
            f"""
            <div style="color:{colors['text']}; font-size:12px; line-height:1.7;">
            <p><b>Stock-Bond Regime Switch</b> — When stock-bond correlation (SPY vs TLT) is negative
            (normal regime), hold SPY. When it turns positive (inflation/crisis regime), switch to
            a safe haven (GLD, TLT, or Cash). Tests if monitoring this single correlation adds value.</p>

            <p><b>Risk-Off on High Correlation</b> — When the average correlation across all assets
            rises above a threshold (everything moving together = stress), reduce to safe haven.
            Return to SPY when correlations normalize. Tests crisis detection.</p>

            <p><b>Dynamic Safe Haven</b> — Always hold SPY, but dynamically choose the hedge asset
            based on which has the most negative correlation to SPY right now. Adapts the hedge
            as regimes change (bonds in deflation, gold in inflation, etc.).</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    available_assets = [c for c in returns.columns if returns[c].notna().sum() > 100]

    col1, col2 = st.columns(2)
    with col1:
        corr_strat = st.selectbox("Strategy", [
            "Stock-Bond Regime Switch",
            "Risk-Off on High Correlation",
            "Dynamic Safe Haven",
        ], key="corr_bt_strat")
    with col2:
        primary_asset = st.selectbox("Primary asset (risk-on)",
                                      available_assets,
                                      index=available_assets.index("S&P 500") if "S&P 500" in available_assets else 0,
                                      key="corr_bt_primary")

    col3, col4, col5 = st.columns(3)
    with col3:
        corr_window = st.slider("Lookback (days)", 20, 120, 60, 10, key="corr_bt_window")
    with col4:
        if "high corr" in corr_strat.lower():
            corr_threshold = st.slider("Go to safe haven when avg corr above", 0.2, 0.8, 0.5, 0.05,
                                       key="corr_bt_thresh",
                                       help="Hold primary normally. Switch to safe haven when average "
                                            "cross-asset correlation exceeds this (everything moving together = stress).")
        elif "regime" in corr_strat.lower():
            pair_options = [a for a in available_assets if a != primary_asset]
            pair_default = pair_options.index("Long Bonds") if "Long Bonds" in pair_options else 0
            corr_pair = st.selectbox("Monitor correlation of",
                                      pair_options,
                                      index=pair_default, key="corr_bt_pair")
            corr_threshold = st.slider("Go to safe haven when corr rises above", -0.5, 0.8, 0.3, 0.05,
                                       key="corr_bt_thresh",
                                       help=f"Hold {primary_asset} normally. Switch to safe haven when "
                                            f"{primary_asset} vs {corr_pair} correlation rises above this threshold. "
                                            f"Higher = fewer switches, only react to extreme correlation.")
        else:
            corr_threshold = 0
    with col5:
        if "dynamic" in corr_strat.lower():
            hedge_pct = st.slider("Hedge allocation %", 10, 50, 30, 5, key="corr_bt_hedge_pct",
                                  help="Percentage allocated to the dynamic hedge")
            safe_haven = "dynamic"
        else:
            safe_haven = st.selectbox("Safe haven asset",
                                      ["Cash (0%)"] + [a for a in available_assets if a != primary_asset],
                                      key="corr_bt_haven")
            hedge_pct = 30

    if returns.empty or primary_asset not in returns.columns:
        st.warning("Insufficient data.")
        return

    primary_ret = returns[primary_asset]

    # Build haven map from all available assets
    haven_map = {a: returns[a] for a in available_assets if a != primary_asset}

    # Compute rolling correlation for regime switch
    if "regime" in corr_strat.lower():
        pair_asset = corr_pair if "corr_pair" in dir() else "Long Bonds"
        pair_ret = returns.get(pair_asset, pd.Series(dtype=float))
        regime_corr = primary_ret.rolling(corr_window).corr(pair_ret) if not pair_ret.empty else pd.Series(dtype=float)
    else:
        regime_corr = pd.Series(dtype=float)

    # Average cross-asset correlation
    if "high corr" in corr_strat.lower():
        asset_cols = [c for c in available_assets if returns[c].notna().sum() > corr_window]
        avg_corr_series = pd.Series(index=returns.index, dtype=float)
        for i in range(corr_window, len(returns)):
            window_data = returns[asset_cols].iloc[i - corr_window:i]
            corr_mat = window_data.corr()
            mask = np.ones(corr_mat.shape, dtype=bool)
            np.fill_diagonal(mask, False)
            avg_corr_series.iloc[i] = corr_mat.values[mask].mean()
    else:
        avg_corr_series = pd.Series(dtype=float)

    # Run backtest with trade log
    equity = 10000.0
    equity_values = []
    trade_log = []
    current_holding = primary_asset
    last_switch_date = None

    for i in range(corr_window + 1, len(primary_ret)):
        date = primary_ret.index[i]
        r_primary = primary_ret.iloc[i] if not pd.isna(primary_ret.iloc[i]) else 0

        if "regime" in corr_strat.lower():
            if not regime_corr.empty and i < len(regime_corr):
                corr_val = regime_corr.iloc[i - 1]
                should_be_primary = pd.isna(corr_val) or corr_val < corr_threshold
            else:
                should_be_primary = True

        elif "high corr" in corr_strat.lower():
            if i < len(avg_corr_series):
                avg_c = avg_corr_series.iloc[i - 1]
                should_be_primary = pd.isna(avg_c) or avg_c < corr_threshold
            else:
                should_be_primary = True

        elif "dynamic" in corr_strat.lower():
            should_be_primary = True  # always partially in primary
        else:
            should_be_primary = True

        if "dynamic" in corr_strat.lower():
            # Dynamic hedge: primary + best uncorrelated asset
            best_hedge_name = "Cash"
            best_hedge_ret = 0
            best_corr_val = 1.0
            for name, h_ret in haven_map.items():
                if h_ret.empty or i >= len(h_ret):
                    continue
                c = primary_ret.iloc[max(0, i - corr_window):i].corr(h_ret.iloc[max(0, i - corr_window):i])
                if not pd.isna(c) and c < best_corr_val:
                    best_corr_val = c
                    best_hedge_name = name
                    best_hedge_ret = h_ret.iloc[i] if not pd.isna(h_ret.iloc[i]) else 0

            primary_pct = (100 - hedge_pct) / 100
            hedge_frac = hedge_pct / 100
            port_ret = primary_pct * r_primary + hedge_frac * best_hedge_ret
            equity *= (1 + port_ret)
            new_holding = f"{primary_asset} ({100-hedge_pct}%) + {best_hedge_name} ({hedge_pct}%)"
        else:
            if should_be_primary:
                equity *= (1 + r_primary)
                new_holding = primary_asset
            else:
                haven_ret = 0
                if safe_haven != "Cash (0%)" and safe_haven in haven_map:
                    h = haven_map[safe_haven]
                    if i < len(h) and not pd.isna(h.iloc[i]):
                        haven_ret = h.iloc[i]
                equity *= (1 + haven_ret)
                new_holding = safe_haven if safe_haven != "Cash (0%)" else "Cash"

        # Log switches
        if new_holding != current_holding:
            if last_switch_date:
                trade_log.append({
                    "Date": date.strftime("%Y-%m-%d"),
                    "Action": f"Switch to {new_holding}",
                    "From": current_holding,
                    "To": new_holding,
                })
            current_holding = new_holding
            last_switch_date = date

        equity_values.append({"Date": date, "Equity": equity})

    if not equity_values:
        st.info("No results.")
        return

    eq_df = pd.DataFrame(equity_values)

    # Benchmark
    bh_equity = (1 + primary_ret.iloc[corr_window + 1:].fillna(0)).cumprod() * 10000
    bh_df = pd.DataFrame({"Date": bh_equity.index, "BuyHold": bh_equity.values})

    total_return = (eq_df["Equity"].iloc[-1] / 10000 - 1) * 100
    bh_return = (bh_equity.iloc[-1] / 10000 - 1) * 100
    eq_s = eq_df.set_index("Date")["Equity"]
    max_dd = ((eq_s - eq_s.cummax()) / eq_s.cummax() * 100).min()
    bh_max_dd = ((bh_equity - bh_equity.cummax()) / bh_equity.cummax() * 100).min()
    num_switches = len(trade_log)

    # Count days in primary vs safe haven
    days_in_primary = sum(1 for ev in equity_values if True)  # need to track
    # Recompute from trade log - count based on holding periods
    primary_days = 0
    haven_days = 0
    for ev_i, ev in enumerate(equity_values):
        # Check what was held on this day by replaying
        pass
    # Simpler: track in the loop above. For now, estimate from trade log
    total_bt_days = len(equity_values)
    # We logged current_holding at end. Count from equity_values metadata isn't available.
    # Add percentage based on switches timing
    pct_in_primary = 100  # fallback
    if "regime" in corr_strat.lower() or "high corr" in corr_strat.lower():
        # Re-estimate: count days where signal says primary
        primary_count = 0
        for i in range(corr_window + 1, len(primary_ret)):
            if "regime" in corr_strat.lower():
                if not regime_corr.empty and i < len(regime_corr):
                    cv = regime_corr.iloc[i - 1]
                    if pd.isna(cv) or cv < corr_threshold:
                        primary_count += 1
                else:
                    primary_count += 1
            elif "high corr" in corr_strat.lower():
                if i < len(avg_corr_series):
                    ac = avg_corr_series.iloc[i - 1]
                    if pd.isna(ac) or ac < corr_threshold:
                        primary_count += 1
                else:
                    primary_count += 1
        pct_in_primary = round(primary_count / max(total_bt_days, 1) * 100, 1)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    for col, label, val, fmt, clr in [
        (k1, "Strategy", total_return, "+.1f", colors["green"] if total_return > 0 else colors["red"]),
        (k2, f"B&H {primary_asset}", bh_return, "+.1f", colors["green"] if bh_return > 0 else colors["red"]),
        (k3, "Strategy Max DD", max_dd, ".1f", colors["red"]),
        (k4, "B&H Max DD", bh_max_dd, ".1f", colors["text_muted"]),
        (k5, "Switches", num_switches, "d", colors["text"]),
        (k6, f"In {primary_asset}", pct_in_primary, ".0f", colors["text"]),
    ]:
        sfx = "%" if "Switch" not in label else ""
        with col:
            st.markdown(
                f'<div class="factor-card" style="text-align:center; padding:8px;">'
                f'<div style="font-size:10px; color:{colors["text_muted"]};">{label}</div>'
                f'<div style="font-size:18px; font-weight:700; color:{clr};">{val:{fmt}}{sfx}</div>'
                f'</div>', unsafe_allow_html=True)

    # Current holding
    st.caption(f"Currently holding: **{current_holding}**")

    eq_line = alt.Chart(eq_df).mark_line(strokeWidth=2, color="#3D85C6").encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
        y=alt.Y("Equity:Q", title="Portfolio ($)"),
        tooltip=[alt.Tooltip("Equity:Q", format="$,.0f"), "Date:T"],
    )
    bh_line = alt.Chart(bh_df).mark_line(strokeWidth=1, opacity=0.5, color=colors["text_muted"]).encode(
        x="Date:T", y="BuyHold:Q",
        tooltip=[alt.Tooltip("BuyHold:Q", format="$,.0f"), "Date:T"],
    )
    st.altair_chart(_style_chart(bh_line + eq_line, colors, 280), use_container_width=True)

    # Drawdown
    dd = (eq_s - eq_s.cummax()) / eq_s.cummax() * 100
    dd_df = pd.DataFrame({"Date": dd.index, "Strategy": dd.values})
    bh_dd = (bh_equity - bh_equity.cummax()) / bh_equity.cummax() * 100
    bh_dd_df = pd.DataFrame({"Date": bh_dd.index, "BH": bh_dd.values})
    dd_area = alt.Chart(dd_df).mark_area(opacity=0.4, color="#3D85C6",
        line={"color": "#3D85C6", "strokeWidth": 1}).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")), y="Strategy:Q")
    bh_dd_line = alt.Chart(bh_dd_df).mark_line(strokeWidth=1, opacity=0.4, color=colors["text_muted"]).encode(
        x="Date:T", y="BH:Q")
    st.altair_chart(_style_chart(bh_dd_line + dd_area, colors, 150), use_container_width=True)

    st.caption(f"Blue = strategy, Grey = buy & hold {primary_asset}. Backtests ignore costs/slippage.")

    # Trade log
    if trade_log:
        with st.expander(f"Trade Log ({num_switches} switches)", expanded=False):
            st.dataframe(pd.DataFrame(trade_log), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Tab 3: AC Regime Map
# ---------------------------------------------------------------------------

def _build_ac_group_options() -> dict[str, list[str] | None]:
    """Build dict of group name → ticker list for AC regime analysis.
    Returns None for the default intermarket group.
    """
    options = {"Intermarket (default)": None}
    config = st.session_state.get("config", {})

    # Custom groups
    for group in config.get("custom_groups", []):
        name = group.get("name", "")
        tickers = group.get("tickers", [])
        if tickers:
            options[f"Custom: {name}"] = tickers

    # Strategies
    strat_holdings = st.session_state.get("strategy_holdings", {})
    for strat in config.get("strategies", []):
        sid = strat["strategy_id"]
        name = strat.get("name", str(sid))
        holdings = strat_holdings.get(sid, [])
        if holdings:
            options[f"Strategy: {name}"] = holdings

    # Screens
    screen_holdings = st.session_state.get("screen_holdings", {})
    for scr in config.get("screens", []):
        sid = scr["screen_id"]
        name = scr.get("name", str(sid))
        holdings = screen_holdings.get(sid, [])
        if holdings:
            options[f"Screen: {name}"] = holdings

    # Rankings
    ranking_data = st.session_state.get("ranking_data", {})
    for rnk in config.get("rankings", []):
        rid = rnk["ranking_id"]
        name = rnk.get("name", str(rid))
        max_h = rnk.get("max_holdings", 25)
        holdings = ranking_data.get(rid, [])[:max_h]
        if holdings:
            options[f"Ranking: {name}"] = holdings

    return options


def _render_ac_regime_tab(colors: dict, theme: str):
    """Autocorrelation regime map — heatmap + regime table."""

    st.caption(
        "Rolling autocorrelation identifies whether assets are trending (positive AC → momentum works) "
        "or mean-reverting (negative AC → reversion works). Directly informs strategy selection."
    )

    with st.expander("How Autocorrelation Regimes Work"):
        st.markdown("""
**Autocorrelation** measures how today's return relates to past returns:

- **Positive AC (> 0.1)** → **Trending regime**. Returns follow previous returns.
  Momentum/trend-following strategies are favored. Example: a stock rising today is likely to rise tomorrow.

- **Negative AC (< -0.1)** → **Mean-reverting regime**. Returns tend to reverse.
  Mean-reversion/contrarian strategies are favored. Example: a stock that fell today is likely to bounce tomorrow.

- **Near zero** → **Random walk / No clear regime**. Neither momentum nor reversion has an edge.

**Lag interpretation:**
- **Lag 1 (Daily)** — Short-term microstructure. Captures intraday/overnight momentum or reversal.
- **Lag 5 (Weekly)** — Medium-term. Captures weekly trend persistence.
- **Lag 21 (Monthly)** — Longer-term. Captures monthly regime tendencies.

**Practical use:** When AC is strongly positive for an asset, increase trend-following exposure.
When AC turns negative, switch to mean-reversion overlays or reduce position size.
        """)

    # ---- Group Selector ----
    group_options = _build_ac_group_options()
    group_names = list(group_options.keys())

    col_group, col_info = st.columns([3, 7])
    with col_group:
        selected_group = st.selectbox(
            "Analyze tickers from",
            group_names,
            index=0,
            key="ac_group_select",
        )

    selected_tickers = group_options[selected_group]

    with col_info:
        if selected_tickers:
            ticker_count = len(selected_tickers)
            preview = ", ".join(selected_tickers[:8])
            if ticker_count > 8:
                preview += f" ... ({ticker_count} total)"
            st.caption(f"Tickers: {preview}")
        else:
            st.caption("12 intermarket ETFs: SPY, QQQ, IWM, TLT, GLD, USO, UUP, EEM, HYG, VNQ, XLE, BTC")

    # Convert to tuple for caching (hashable)
    custom_tuple = tuple(selected_tickers) if selected_tickers else None

    with st.spinner("Computing autocorrelation regimes..."):
        data = fetch_ac_regime_data(window=60, custom_tickers=custom_tuple)

    if not data:
        st.warning("Unable to compute autocorrelation data. Click 🔄 to refresh.")
        return

    current_df = data["current"]
    heatmap_data = data["heatmap"]

    # ---- Current Regime Table ----
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 8px 0;">'
        f'Current Regime Summary</div>',
        unsafe_allow_html=True,
    )

    if not current_df.empty:
        # Build HTML table for regime display
        rows_html = ""
        for _, row in current_df.iterrows():
            asset = row["Asset"]
            regime = row.get("Regime", "N/A")

            # Regime badge colors
            if regime == "Trending":
                badge_bg = "#27AE6020"
                badge_color = colors["green"]
                badge_icon = "📈"
            elif regime == "Mean-Reverting":
                badge_bg = "#E0666620"
                badge_color = colors["red"]
                badge_icon = "🔄"
            else:
                badge_bg = f"{colors['text_muted']}15"
                badge_color = colors["text_muted"]
                badge_icon = "➖"

            # AC values with color coding
            ac_cells = ""
            for lag_label in AC_LAGS:
                val = row.get(lag_label)
                if val is not None:
                    if val > 0.1:
                        val_color = colors["green"]
                    elif val < -0.1:
                        val_color = colors["red"]
                    else:
                        val_color = colors["text_muted"]
                    ac_cells += f'<td style="text-align:center; color:{val_color}; font-weight:600;">{val:+.3f}</td>'
                else:
                    ac_cells += f'<td style="text-align:center; color:{colors["text_muted"]};">—</td>'

            rows_html += f"""
            <tr style="border-bottom:1px solid {colors['border']}22;">
                <td style="padding:6px 8px; font-weight:500;">{asset}</td>
                {ac_cells}
                <td style="text-align:center;">
                    <span style="background:{badge_bg}; color:{badge_color}; padding:2px 8px;
                                 border-radius:4px; font-size:11px; font-weight:600;">
                        {badge_icon} {regime}
                    </span>
                </td>
            </tr>"""

        table_html = f"""
        <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; font-size:13px; color:{colors['text']};">
            <thead>
                <tr style="border-bottom:2px solid {colors['border']}44;">
                    <th style="text-align:left; padding:6px 8px; color:{colors['text_muted']}; font-size:11px; text-transform:uppercase;">Asset</th>
                    <th style="text-align:center; color:{colors['text_muted']}; font-size:11px; text-transform:uppercase;">AC(1) Daily</th>
                    <th style="text-align:center; color:{colors['text_muted']}; font-size:11px; text-transform:uppercase;">AC(5) Weekly</th>
                    <th style="text-align:center; color:{colors['text_muted']}; font-size:11px; text-transform:uppercase;">AC(21) Monthly</th>
                    <th style="text-align:center; color:{colors['text_muted']}; font-size:11px; text-transform:uppercase;">Regime</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>"""
        st.markdown(table_html, unsafe_allow_html=True)

    st.caption(
        "Regime based on daily (lag-1) autocorrelation: > 0.1 = Trending, < -0.1 = Mean-Reverting, else Neutral. "
        "Rolling 60-day window."
    )

    # ---- Heatmap ----
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 8px 0;">'
        f'Autocorrelation Heatmap Over Time</div>',
        unsafe_allow_html=True,
    )

    lag_options = list(AC_LAGS.keys())
    selected_lag = st.radio("Lag period", lag_options, index=0, horizontal=True, key="ac_lag_select")

    hm_df = heatmap_data.get(selected_lag, pd.DataFrame())
    if hm_df.empty:
        st.caption("No heatmap data available for this lag.")
        return

    # Use last 252 trading days (1 year) for the heatmap
    hm_df = hm_df.tail(252)

    # Resample to weekly for clearer color blocks (daily is too dense)
    hm_weekly = hm_df.resample("W-FRI").last().dropna(how="all")

    # Melt for Altair
    hm_reset = hm_weekly.reset_index()
    hm_reset.columns = ["Date"] + list(hm_weekly.columns)
    melted = hm_reset.melt(id_vars="Date", var_name="Asset", value_name="AC")
    melted = melted.dropna(subset=["AC"])

    # Add Date_end for rect width (each block = 1 week)
    melted["Date_end"] = melted["Date"] + pd.Timedelta(days=7)

    if melted.empty:
        st.caption("Insufficient data for heatmap.")
        return

    # Sort assets by their current AC value for better visual grouping
    if not current_df.empty:
        asset_order = current_df["Asset"].tolist()
    else:
        asset_order = sorted(melted["Asset"].unique())

    heatmap = (
        alt.Chart(melted)
        .mark_rect()
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-45)),
            x2="Date_end:T",
            y=alt.Y("Asset:N", title=None, sort=asset_order,
                     axis=alt.Axis(labelFontSize=11)),
            color=alt.Color(
                "AC:Q",
                scale=alt.Scale(
                    domain=[-0.3, 0, 0.3],
                    range=["#4A90D9", "#1a1a2e" if theme == "dark" else "#ffffff", "#E06666"],
                ),
                legend=alt.Legend(title="AC", orient="right"),
            ),
            tooltip=[
                alt.Tooltip("Asset:N"),
                alt.Tooltip("AC:Q", format="+.3f"),
                alt.Tooltip("Date:T", format="%b %d, %Y"),
            ],
        )
        .properties(height=max(280, len(asset_order) * 28))
    )

    bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
    styled = heatmap.configure(
        background=bg_color,
    ).configure_axis(
        labelColor=colors["text_muted"],
        titleColor=colors["text_muted"],
        gridColor=f"{colors['border']}22",
        domainColor=f"{colors['border']}44",
    ).configure_legend(
        labelColor=colors["text_muted"],
        titleColor=colors["text_muted"],
    )

    st.altair_chart(styled, use_container_width=True)

    st.caption(
        f"Weekly sampled over the last year (~52 weeks). Red = trending (positive AC), "
        f"Blue = mean-reverting (negative AC). Selected lag: {selected_lag}."
    )

    # ---- Individual Asset AC Time Series ----
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 8px 0;">'
        f'Autocorrelation Time Series</div>',
        unsafe_allow_html=True,
    )

    asset_names = sorted(hm_df.columns.tolist())
    selected_asset = st.selectbox("Select asset", asset_names,
                                   index=asset_names.index("S&P 500") if "S&P 500" in asset_names else 0,
                                   key="ac_asset_select")

    # Show all three lags for the selected asset
    ts_frames = []
    for lag_label in AC_LAGS:
        lag_hm = heatmap_data.get(lag_label, pd.DataFrame())
        if selected_asset in lag_hm.columns:
            series = lag_hm[selected_asset].dropna().tail(504)  # 2 years
            ts_df = series.reset_index()
            ts_df.columns = ["Date", "AC"]
            ts_df["Lag"] = lag_label
            ts_frames.append(ts_df)

    if ts_frames:
        ts_all = pd.concat(ts_frames, ignore_index=True)

        lag_colors = {
            "Daily (lag-1)": "#E06666",
            "Weekly (lag-5)": "#3D85C6",
            "Monthly (lag-21)": "#93C47D",
        }
        domain = list(lag_colors.keys())
        range_vals = list(lag_colors.values())

        ac_lines = (
            alt.Chart(ts_all)
            .mark_line(strokeWidth=1.5)
            .encode(
                x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %Y")),
                y=alt.Y("AC:Q", title="Autocorrelation",
                         scale=alt.Scale(domain=[-0.4, 0.4])),
                color=alt.Color("Lag:N",
                                scale=alt.Scale(domain=domain, range=range_vals),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=[
                    alt.Tooltip("Lag:N"),
                    alt.Tooltip("AC:Q", format="+.3f"),
                    alt.Tooltip("Date:T", format="%b %d, %Y"),
                ],
            )
        )

        # Zero line
        zero = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[6, 3], strokeWidth=1, color=colors["text_muted"])
            .encode(y="y:Q")
        )

        # Threshold lines at +/- 0.1
        thresh_pos = (
            alt.Chart(pd.DataFrame({"y": [0.1]}))
            .mark_rule(strokeDash=[3, 3], strokeWidth=0.8, color=colors["green"], opacity=0.5)
            .encode(y="y:Q")
        )
        thresh_neg = (
            alt.Chart(pd.DataFrame({"y": [-0.1]}))
            .mark_rule(strokeDash=[3, 3], strokeWidth=0.8, color=colors["red"], opacity=0.5)
            .encode(y="y:Q")
        )

        # Price overlay (right y-axis)
        close_df = data.get("close", pd.DataFrame())
        price_layer = None
        if selected_asset in close_df.columns:
            price_data = close_df[selected_asset].dropna().tail(504)
            if not price_data.empty:
                pr_df = price_data.reset_index()
                pr_df.columns = ["Date", "Price"]
                price_layer = (
                    alt.Chart(pr_df)
                    .mark_line(strokeWidth=1, opacity=0.3, color=colors["green"])
                    .encode(
                        x="Date:T",
                        y=alt.Y("Price:Q", title=selected_asset,
                                axis=alt.Axis(orient="right")),
                        tooltip=[alt.Tooltip("Price:Q", format=",.2f"), "Date:T"],
                    )
                )

        base_chart = zero + thresh_neg + thresh_pos + ac_lines
        if price_layer:
            chart = alt.layer(base_chart, price_layer).resolve_scale(y="independent")
        else:
            chart = base_chart

        styled_ts = chart.properties(height=300).configure(
            background=bg_color,
        ).configure_axis(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
            gridColor=f"{colors['border']}22",
            domainColor=f"{colors['border']}44",
        ).configure_legend(
            labelColor=colors["text_muted"],
            titleColor=colors["text_muted"],
        )

        st.altair_chart(styled_ts, use_container_width=True)

        st.caption(
            f"{selected_asset} — autocorrelation at 3 lags over the last 2 years. "
            f"Green dashed = +0.1 trending threshold, red dashed = -0.1 mean-reverting threshold. "
            f"Faint green line = price overlay."
        )
    else:
        st.caption(f"No autocorrelation data available for {selected_asset}.")


def _placeholder(colors: dict, title: str, description: str):
    st.markdown(
        f"""
        <div class="factor-card" style="text-align:center; padding:40px 20px;">
            <div style="font-size:18px; font-weight:600; color:{colors['text_header']}; margin-bottom:8px;">
                {title}
            </div>
            <div style="font-size:13px; color:{colors['text_muted']};">
                {description}
            </div>
            <div style="font-size:12px; color:{colors['text_muted']}; margin-top:16px;">
                Coming soon — this feature is under development.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _style_chart(chart, colors: dict, height: int = 280):
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


# ---------------------------------------------------------------------------
# Tab 1: Sector Rotation (RRG)
# ---------------------------------------------------------------------------

def _render_rrg_tab(colors: dict, theme: str):
    """Relative Rotation Graph for sector ETFs."""

    st.caption(
        "The Relative Rotation Graph plots each sector's relative strength vs SPY. "
        "Sectors rotate clockwise: Improving → Leading → Weakening → Lagging. "
        "Trail lines show each sector's path over the past weeks."
    )

    with st.expander("How RRG Works — Detailed Methodology", expanded=False):
        st.markdown(
            f"""
            <div style="color:{colors['text']}; font-size:12px; line-height:1.8;">
                <p><b>RS-Ratio (x-axis)</b> — Measures whether a sector is outperforming or underperforming
                SPY <i>relative to its own history</i>.</p>
                <p style="margin-left:16px; color:{colors['text_muted']};">
                Formula: <code>RS-Ratio = (Sector/SPY) / 52-week MA of (Sector/SPY) × 100</code><br>
                Above 100 = sector is outperforming SPY more than its 52-week average.<br>
                Below 100 = sector is underperforming relative to its own norm.</p>

                <p><b>RS-Momentum (y-axis)</b> — Measures how fast the RS-Ratio is changing — is relative
                strength <i>accelerating</i> or <i>decelerating</i>?</p>
                <p style="margin-left:16px; color:{colors['text_muted']};">
                Formula: <code>RS-Momentum = RS-Ratio today / RS-Ratio N weeks ago × 100</code><br>
                Where N = trail length (default 4 weeks).<br>
                Above 100 = relative strength is improving (accelerating).<br>
                Below 100 = relative strength is fading (decelerating).</p>

                <p><b>Clockwise Rotation</b> — Sectors naturally rotate through 4 quadrants:</p>
                <ul>
                    <li><span style="color:#3D85C6; font-weight:600;">Improving</span> (top-left) —
                        RS-Ratio below 100 but rising. The sector is still underperforming overall,
                        but momentum is turning positive. <i>Early accumulation zone.</i></li>
                    <li><span style="color:#4CAF50; font-weight:600;">Leading</span> (top-right) —
                        RS-Ratio above 100 and still rising. Strong outperformance with
                        positive momentum. <i>Best relative performance — hold or add.</i></li>
                    <li><span style="color:#E8A838; font-weight:600;">Weakening</span> (bottom-right) —
                        RS-Ratio above 100 but declining. Still outperforming but momentum fading.
                        <i>Take profits, reduce exposure.</i></li>
                    <li><span style="color:#E06666; font-weight:600;">Lagging</span> (bottom-left) —
                        RS-Ratio below 100 and declining. Underperforming with negative momentum.
                        <i>Avoid or underweight.</i></li>
                </ul>

                <p><b>Trail Lines</b> — The thin lines behind each dot show where the sector was
                over the past N weeks. Follow the trail to see the rotation direction. A sector
                moving clockwise from Lagging to Improving is a potential early buy signal.</p>

                <p style="color:{colors['text_muted']}; font-style:italic;">
                Methodology by Julius de Kempenaer (JdK RS-Ratio). Used by Bloomberg, StockCharts,
                and institutional traders for sector rotation analysis.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    trail_weeks = st.slider("Trail length (weeks)", 1, 8, 4, 1, key="rrg_trail",
                            help="Number of weeks to show rotation trail")

    with st.spinner("Downloading sector data — this may take a moment on first load..."):
        data = fetch_rrg_data(trail_weeks)

    if not data:
        st.warning("Unable to compute sector rotation data. This usually means the data download timed out. "
                   "Click the 🔄 button above to retry.")
        return

    current = data["current"]
    trails = data["trails"]

    # RRG scatter plot with quadrant shading
    # Quadrant backgrounds
    x_min = min(current["RS_Ratio"].min(), 97)
    x_max = max(current["RS_Ratio"].max(), 103)
    y_min = min(current["RS_Momentum"].min(), 97)
    y_max = max(current["RS_Momentum"].max(), 103)

    # Add some padding
    x_pad = (x_max - x_min) * 0.1
    y_pad = (y_max - y_min) * 0.1
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    quadrants = pd.DataFrame([
        {"x": x_min, "x2": 100, "y": 100, "y2": y_max, "Quadrant": "Improving", "color": "#3D85C620"},
        {"x": 100, "x2": x_max, "y": 100, "y2": y_max, "Quadrant": "Leading", "color": "#4CAF5020"},
        {"x": 100, "x2": x_max, "y": y_min, "y2": 100, "Quadrant": "Weakening", "color": "#E8A83820"},
        {"x": x_min, "x2": 100, "y": y_min, "y2": 100, "Quadrant": "Lagging", "color": "#E0666620"},
    ])

    quad_rects = (
        alt.Chart(quadrants)
        .mark_rect()
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[x_min, x_max])),
            x2="x2:Q",
            y=alt.Y("y:Q", scale=alt.Scale(domain=[y_min, y_max])),
            y2="y2:Q",
            color=alt.Color("color:N", scale=None),
            opacity=alt.value(0.15),
        )
    )

    # Quadrant labels
    ql_data = pd.DataFrame([
        {"x": (x_min + 100) / 2, "y": (100 + y_max) / 2, "label": "IMPROVING"},
        {"x": (100 + x_max) / 2, "y": (100 + y_max) / 2, "label": "LEADING"},
        {"x": (100 + x_max) / 2, "y": (y_min + 100) / 2, "label": "WEAKENING"},
        {"x": (x_min + 100) / 2, "y": (y_min + 100) / 2, "label": "LAGGING"},
    ])
    quad_labels = (
        alt.Chart(ql_data)
        .mark_text(fontSize=10, opacity=0.25, fontWeight=600)
        .encode(
            x="x:Q", y="y:Q",
            text="label:N",
            color=alt.value(colors["text_muted"]),
        )
    )

    # Center crosshair at (100, 100)
    h_line = (
        alt.Chart(pd.DataFrame({"y": [100]}))
        .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["text_muted"], opacity=0.5)
        .encode(y="y:Q")
    )
    v_line = (
        alt.Chart(pd.DataFrame({"x": [100]}))
        .mark_rule(strokeDash=[4, 4], strokeWidth=1, color=colors["text_muted"], opacity=0.5)
        .encode(x="x:Q")
    )

    # Current positions — colored by quadrant
    quad_colors = {"Leading": "#4CAF50", "Weakening": "#E8A838", "Lagging": "#E06666", "Improving": "#3D85C6"}

    points = (
        alt.Chart(current)
        .mark_circle(size=120)
        .encode(
            x=alt.X("RS_Ratio:Q", title="RS-Ratio (vs 52-week avg)",
                     scale=alt.Scale(domain=[x_min, x_max])),
            y=alt.Y("RS_Momentum:Q", title="RS-Momentum",
                     scale=alt.Scale(domain=[y_min, y_max])),
            color=alt.Color("Quadrant:N",
                            scale=alt.Scale(
                                domain=list(quad_colors.keys()),
                                range=list(quad_colors.values()),
                            ),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["Name:N", "Ticker:N",
                     alt.Tooltip("RS_Ratio:Q", format=".1f"),
                     alt.Tooltip("RS_Momentum:Q", format=".1f"),
                     alt.Tooltip("Ret_1M:Q", format="+.1f", title="1M Ret"),
                     alt.Tooltip("Ret_3M:Q", format="+.1f", title="3M Ret")],
        )
    )

    # Labels on points
    labels = (
        alt.Chart(current)
        .mark_text(dy=-12, fontSize=10, fontWeight=600)
        .encode(
            x="RS_Ratio:Q",
            y="RS_Momentum:Q",
            text="Ticker:N",
            color=alt.value(colors["text"]),
        )
    )

    # Trail lines
    trail_layers = []
    for ticker, pts in trails.items():
        if len(pts) < 2:
            continue
        trail_df = pd.DataFrame(pts)
        trail_df["order"] = range(len(trail_df))
        quad = current[current["Ticker"] == ticker]["Quadrant"].iloc[0] if ticker in current["Ticker"].values else "Lagging"
        trail_color = quad_colors.get(quad, colors["text_muted"])

        trail_line = (
            alt.Chart(trail_df)
            .mark_line(strokeWidth=1.5, opacity=0.4, color=trail_color)
            .encode(
                x=alt.X("RS_Ratio:Q", scale=alt.Scale(domain=[x_min, x_max])),
                y=alt.Y("RS_Momentum:Q", scale=alt.Scale(domain=[y_min, y_max])),
                order="order:Q",
            )
        )
        trail_layers.append(trail_line)

    chart = quad_rects + quad_labels + h_line + v_line
    for tl in trail_layers:
        chart = chart + tl
    chart = chart + points + labels

    st.altair_chart(_style_chart(chart, colors, 450), use_container_width=True)

    st.caption(
        "Based on JdK RS-Ratio methodology by Julius de Kempenaer. "
        "Data: weekly closes from Yahoo Finance."
    )

    # Sector table
    st.markdown(
        f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
        f'Sector Summary</div>',
        unsafe_allow_html=True,
    )

    rows_html = ""
    for _, row in current.sort_values("RS_Ratio", ascending=False).iterrows():
        qc = quad_colors.get(row["Quadrant"], colors["text_muted"])
        ret1_c = colors["green"] if row["Ret_1M"] > 0 else colors["red"]
        ret3_c = colors["green"] if row["Ret_3M"] > 0 else colors["red"]
        rows_html += f"""
        <tr style="border-bottom:1px solid {colors['border']}33;">
            <td style="padding:6px 8px; font-weight:600; color:{colors['text']};">{row['Ticker']}</td>
            <td style="padding:6px 8px; color:{colors['text_muted']};">{row['Name']}</td>
            <td style="padding:6px 8px; text-align:right;">{row['RS_Ratio']:.1f}</td>
            <td style="padding:6px 8px; text-align:right;">{row['RS_Momentum']:.1f}</td>
            <td style="padding:6px 8px; text-align:center;">
                <span style="padding:2px 8px; border-radius:8px; font-size:11px; font-weight:600;
                      background:{qc}20; color:{qc};">{row['Quadrant']}</span>
            </td>
            <td style="padding:6px 8px; text-align:right; color:{ret1_c};">{row['Ret_1M']:+.1f}%</td>
            <td style="padding:6px 8px; text-align:right; color:{ret3_c};">{row['Ret_3M']:+.1f}%</td>
        </tr>"""

    st.markdown(
        f"""
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr style="border-bottom:2px solid {colors['border']};">
                    <th style="padding:8px; text-align:left; color:{colors['text_muted']}; font-size:11px;">Ticker</th>
                    <th style="padding:8px; text-align:left; color:{colors['text_muted']}; font-size:11px;">Sector</th>
                    <th style="padding:8px; text-align:right; color:{colors['text_muted']}; font-size:11px;">RS-Ratio</th>
                    <th style="padding:8px; text-align:right; color:{colors['text_muted']}; font-size:11px;">RS-Mom</th>
                    <th style="padding:8px; text-align:center; color:{colors['text_muted']}; font-size:11px;">Quadrant</th>
                    <th style="padding:8px; text-align:right; color:{colors['text_muted']}; font-size:11px;">1M</th>
                    <th style="padding:8px; text-align:right; color:{colors['text_muted']}; font-size:11px;">3M</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    # RRG Backtester
    _render_rrg_backtest(colors, theme)


def _render_rrg_backtest(colors: dict, theme: str):
    """Backtest sector rotation strategies based on RRG quadrants."""

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:16px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Sector Rotation Backtester</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Strategy Descriptions", expanded=False):
        st.markdown(
            f"""
            <div style="color:{colors['text']}; font-size:12px; line-height:1.7;">
            <p><b>Buy Leading</b> — Hold the sector ETF with the highest RS-Ratio that is in the
            Leading quadrant. If no sector is Leading, move to cash/defensive. Rebalances weekly.
            <i>Rides the strongest sector.</i></p>

            <p><b>Buy Improving → sell Weakening</b> — Hold sectors in Improving or Leading quadrants.
            Exit when entering Weakening. Catches the full rotation cycle from early recovery to peak.</p>

            <p><b>Avoid Lagging</b> — Equal-weight all sectors EXCEPT those in the Lagging quadrant.
            Passive approach — just cut the losers.</p>

            <p style="color:{colors['text_muted']}; font-weight:600; text-transform:uppercase; font-size:11px; margin-top:12px;">Ranking Strategies</p>

            <p><b>Top N by RS-Ratio</b> — Equal-weight the top N sectors by RS-Ratio.
            Pure relative strength — hold the sectors outperforming SPY the most.</p>

            <p><b>Top N by RS-Momentum</b> — Equal-weight the top N sectors by RS-Momentum.
            Buys sectors with the fastest <i>improving</i> relative strength — catches sectors
            accelerating into leadership regardless of current ratio level.</p>

            <p><b>Top N by Combined Score</b> — Ranks sectors by (RS-Ratio + RS-Momentum) / 2.
            Balances current strength with acceleration — prefers sectors that are both
            strong AND getting stronger.</p>

            <p style="color:{colors['text_muted']}; font-weight:600; text-transform:uppercase; font-size:11px; margin-top:12px;">Contrarian</p>

            <p><b>Buy Lagging (contrarian)</b> — Hold the top N sectors in the Lagging quadrant
            (weakest relative strength). Bets on mean reversion — beaten-down sectors
            may bounce. Useful as a reference to test if momentum or contrarian wins.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        strategy = st.selectbox("Strategy", [
            "Buy Leading",
            "Buy Improving → sell Weakening",
            "Avoid Lagging (equal-weight rest)",
            "Top N by RS-Ratio",
            "Top N by RS-Momentum",
            "Top N by Combined Score",
            "Buy Lagging (contrarian)",
        ], key="rrg_bt_strat")
    with col2:
        top_n = st.slider("Hold N sectors", 1, 8, 3, 1, key="rrg_bt_topn",
                          help="Number of sectors to hold (equal-weighted)")
        cash_etf = st.selectbox("When no signal, hold:",
                                ["Cash (0%)", "SPY", "TLT", "GLD"],
                                key="rrg_bt_cash")
    with col3:
        benchmark = st.selectbox("Benchmark", ["SPY", "Equal-weight all sectors"], key="rrg_bt_bench")

    with st.spinner("Computing RRG backtest (10Y weekly data)..."):
        bt_data = fetch_rrg_backtest_data()

    if not bt_data:
        st.warning("Unable to fetch backtest data.")
        return

    prices = bt_data["prices"]
    quadrants = bt_data["quadrants"]
    rs_ratios = bt_data.get("rs_ratios", pd.DataFrame())
    rs_momentums = bt_data.get("rs_momentums", pd.DataFrame())

    # Align dates
    common_dates = prices.index.intersection(quadrants.index)
    prices = prices.loc[common_dates]
    quadrants = quadrants.loc[common_dates]
    if not rs_ratios.empty:
        rs_ratios = rs_ratios.reindex(common_dates)
    if not rs_momentums.empty:
        rs_momentums = rs_momentums.reindex(common_dates)

    # Get cash ETF prices
    cash_ticker = None
    if "SPY" in cash_etf:
        cash_ticker = "SPY"
    elif "TLT" in cash_etf:
        cash_ticker = "TLT"
    elif "GLD" in cash_etf:
        cash_ticker = "GLD"

    # Compute weekly returns for each sector
    sector_tickers = [t for t in SECTOR_ETFS if t in prices.columns]
    sector_returns = prices[sector_tickers].pct_change(fill_method=None)
    spy_returns = prices["SPY"].pct_change(fill_method=None)
    cash_returns = prices[cash_ticker].pct_change(fill_method=None) if cash_ticker and cash_ticker in prices.columns else pd.Series(0, index=prices.index)

    # Strategy flags
    import re
    s_lower = strategy.lower()
    is_leading = "leading" in s_lower
    is_improving = "improving" in s_lower
    is_avoid = "avoid" in s_lower
    is_rs_ratio = "rs-ratio" in s_lower
    is_rs_mom = "rs-momentum" in s_lower
    is_combined = "combined" in s_lower
    is_contrarian = "lagging" in s_lower and "contrarian" in s_lower

    # Run backtest — compute portfolio return each week
    portfolio_returns = []
    position_log = []  # track what's held each week

    for i in range(1, len(common_dates)):
        date = common_dates[i]
        prev_date = common_dates[i - 1]
        quads = quadrants.loc[prev_date]  # use previous week's signal

        hold = []

        if is_leading:
            # Leading sectors, limited to top_n
            candidates = [t for t in sector_tickers if quads.get(t) == "Leading"]
            if candidates and not rs_ratios.empty:
                scores = rs_ratios.loc[prev_date, candidates].dropna()
                hold = scores.nlargest(min(top_n, len(scores))).index.tolist()
            else:
                hold = candidates[:top_n]

        elif is_improving:
            # Improving + Leading, limited to top_n
            candidates = [t for t in sector_tickers if quads.get(t) in ("Improving", "Leading")]
            if candidates and not rs_momentums.empty:
                scores = rs_momentums.loc[prev_date, candidates].dropna()
                hold = scores.nlargest(min(top_n, len(scores))).index.tolist()
            else:
                hold = candidates[:top_n]

        elif is_avoid:
            # All except Lagging, no limit (use all non-lagging)
            hold = [t for t in sector_tickers if quads.get(t) not in ("Lagging", "")]

        elif is_combined:
            # Top N by (RS-Ratio + RS-Momentum) / 2
            if not rs_ratios.empty and not rs_momentums.empty:
                r = rs_ratios.loc[prev_date, sector_tickers].dropna()
                m = rs_momentums.loc[prev_date, sector_tickers].dropna()
                common = r.index.intersection(m.index)
                if len(common) > 0:
                    combined_score = (r[common] + m[common]) / 2
                    hold = combined_score.nlargest(min(top_n, len(combined_score))).index.tolist()

        elif is_rs_mom:
            # Top N by RS-Momentum
            if not rs_momentums.empty:
                scores = rs_momentums.loc[prev_date, sector_tickers].dropna()
                hold = scores.nlargest(min(top_n, len(scores))).index.tolist()

        elif is_rs_ratio:
            # Top N by RS-Ratio
            if not rs_ratios.empty:
                scores = rs_ratios.loc[prev_date, sector_tickers].dropna()
                hold = scores.nlargest(min(top_n, len(scores))).index.tolist()

        elif is_contrarian:
            # Buy Lagging — bottom N by RS-Ratio (weakest sectors)
            candidates = [t for t in sector_tickers if quads.get(t) == "Lagging"]
            if candidates and not rs_ratios.empty:
                scores = rs_ratios.loc[prev_date, candidates].dropna()
                hold = scores.nsmallest(min(top_n, len(scores))).index.tolist()
            elif candidates:
                hold = candidates[:top_n]

        # Compute return and log positions
        in_cash = False
        if hold:
            valid_hold = [t for t in hold if t in sector_returns.columns]
            ret = sector_returns.loc[date, valid_hold].mean() if valid_hold else 0
            if not valid_hold:
                in_cash = True
        else:
            ret = cash_returns.loc[date] if cash_ticker else 0
            in_cash = True
            valid_hold = []

        position_log.append({
            "Date": date,
            "Positions": len(valid_hold),
            "Holdings": ", ".join(valid_hold) if valid_hold else (cash_ticker or "Cash"),
            "InCash": in_cash,
        })

        portfolio_returns.append({"Date": date, "Return": ret if not pd.isna(ret) else 0})

    if not portfolio_returns:
        st.info("No backtest results.")
        return

    ret_df = pd.DataFrame(portfolio_returns)
    ret_df["Equity"] = (1 + ret_df["Return"]).cumprod() * 10000

    # Benchmark
    if "equal" in benchmark.lower():
        bm_ret = sector_returns[list(SECTOR_ETFS.keys())].mean(axis=1)
    else:
        bm_ret = spy_returns
    bm_equity = (1 + bm_ret.loc[ret_df["Date"]].fillna(0)).cumprod() * 10000
    bm_df = pd.DataFrame({"Date": bm_equity.index, "Benchmark": bm_equity.values})

    # Position stats
    pos_df = pd.DataFrame(position_log)
    avg_positions = pos_df["Positions"].mean()
    pct_in_cash = (pos_df["InCash"].sum() / len(pos_df) * 100) if len(pos_df) > 0 else 0
    pct_invested = 100 - pct_in_cash

    # Stats
    total_return = (ret_df["Equity"].iloc[-1] / 10000 - 1) * 100
    bm_return = (bm_equity.iloc[-1] / 10000 - 1) * 100
    eq_series = ret_df.set_index("Date")["Equity"]
    max_dd = ((eq_series - eq_series.cummax()) / eq_series.cummax() * 100).min()
    bm_max_dd = ((bm_equity - bm_equity.cummax()) / bm_equity.cummax() * 100).min()

    # KPIs
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        c = colors["green"] if total_return > 0 else colors["red"]
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Strategy</div>'
            f'<div style="font-size:18px; font-weight:700; color:{c};">{total_return:+.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k2:
        c = colors["green"] if bm_return > 0 else colors["red"]
        bm_label = "EW Sectors" if "equal" in benchmark.lower() else "SPY"
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">{bm_label}</div>'
            f'<div style="font-size:18px; font-weight:700; color:{c};">{bm_return:+.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k3:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Strategy Max DD</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["red"]};">{max_dd:.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k4:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Benchmark Max DD</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text_muted"]};">{bm_max_dd:.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k5:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Avg Positions</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text"]};">{avg_positions:.1f}</div>'
            f'</div>', unsafe_allow_html=True)
    with k6:
        st.markdown(
            f'<div class="factor-card" style="text-align:center; padding:8px;">'
            f'<div style="font-size:10px; color:{colors["text_muted"]};">Invested</div>'
            f'<div style="font-size:18px; font-weight:700; color:{colors["text"]};">{pct_invested:.0f}%</div>'
            f'<div style="font-size:9px; color:{colors["text_muted"]};">{pct_in_cash:.0f}% in {cash_ticker or "Cash"}</div>'
            f'</div>', unsafe_allow_html=True)

    # Equity chart
    eq_line = alt.Chart(ret_df).mark_line(strokeWidth=2, color="#3D85C6").encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
        y=alt.Y("Equity:Q", title="Portfolio ($)"),
        tooltip=[alt.Tooltip("Equity:Q", format="$,.0f"), "Date:T"],
    )
    bm_line = alt.Chart(bm_df).mark_line(strokeWidth=1, opacity=0.5, color=colors["text_muted"]).encode(
        x="Date:T", y="Benchmark:Q",
        tooltip=[alt.Tooltip("Benchmark:Q", format="$,.0f"), "Date:T"],
    )
    st.altair_chart(_style_chart(bm_line + eq_line, colors, 280), use_container_width=True)

    # Drawdown
    dd_vals = (eq_series - eq_series.cummax()) / eq_series.cummax() * 100
    dd_df = pd.DataFrame({"Date": dd_vals.index, "Strategy": dd_vals.values})
    bm_dd = (bm_equity - bm_equity.cummax()) / bm_equity.cummax() * 100
    bm_dd_df = pd.DataFrame({"Date": bm_dd.index, "BuyHold": bm_dd.values})

    dd_area = alt.Chart(dd_df).mark_area(opacity=0.4, color="#3D85C6",
        line={"color": "#3D85C6", "strokeWidth": 1}).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")),
        y=alt.Y("Strategy:Q", title="Drawdown (%)"),
    )
    bm_dd_line = alt.Chart(bm_dd_df).mark_line(
        strokeWidth=1, opacity=0.4, color=colors["text_muted"]).encode(
        x="Date:T", y="BuyHold:Q")

    st.altair_chart(_style_chart(bm_dd_line + dd_area, colors, 150), use_container_width=True)

    st.caption(
        f"Blue = strategy, Grey = {benchmark}. Weekly rebalancing. Starting capital $10,000. "
        f"Backtests do not account for transaction costs, slippage, or taxes."
    )


# ---------------------------------------------------------------------------
# Tab 2: Correlation Matrix
# ---------------------------------------------------------------------------

def _render_correlation_tab(colors: dict, theme: str):
    """Intermarket correlation matrix."""

    window = st.selectbox("Correlation window",
                          [("20 days (short-term)", 20), ("60 days (medium-term)", 60),
                           ("252 days (1 year)", 252)],
                          index=1, format_func=lambda x: x[0], key="corr_window")[1]

    with st.spinner("Computing correlations..."):
        data = fetch_correlation_matrix(window)

    if not data:
        st.warning("Unable to compute correlation data.")
        return

    matrix = data["matrix"]
    returns = data["returns"]

    # Heatmap
    # Melt the correlation matrix for Altair
    matrix_reset = matrix.reset_index()
    id_col = matrix_reset.columns[0]  # whatever the index column is named
    corr_long = matrix_reset.melt(id_vars=id_col, var_name="Asset2", value_name="Corr")
    corr_long = corr_long.rename(columns={id_col: "Asset1"})

    assets = list(matrix.columns)

    heatmap = (
        alt.Chart(corr_long)
        .mark_rect(stroke=colors["bg_card"], strokeWidth=2)
        .encode(
            x=alt.X("Asset2:N", sort=assets, title=None,
                     axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Asset1:N", sort=assets, title=None),
            color=alt.Color("Corr:Q",
                            scale=alt.Scale(domain=[-1, 0, 1],
                                            range=["#E06666", "#FFFFFF", "#3D85C6"]),
                            legend=alt.Legend(title="Correlation")),
            tooltip=["Asset1:N", "Asset2:N", alt.Tooltip("Corr:Q", format=".2f")],
        )
    )

    # Text overlay
    text = (
        alt.Chart(corr_long)
        .mark_text(fontSize=10, fontWeight=600)
        .encode(
            x=alt.X("Asset2:N", sort=assets),
            y=alt.Y("Asset1:N", sort=assets),
            text=alt.Text("Corr:Q", format=".2f"),
            color=alt.condition(
                (alt.datum.Corr > 0.6) | (alt.datum.Corr < -0.6),
                alt.value("#FFFFFF"),
                alt.value("#1a1a1a"),
            ),
        )
    )

    chart = (
        (heatmap + text)
        .properties(height=450, width=450)
        .configure_view(strokeWidth=0)
        .configure(background=colors["bg_card"])
        .configure_axis(
            labelColor=colors["text_muted"],
            domainColor=colors["border"],
        )
        .configure_legend(
            labelColor=colors["text"],
            titleColor=colors["text"],
        )
    )

    st.altair_chart(chart, use_container_width=True)

    with st.expander("How to Use Correlation Data", expanded=False):
        st.markdown(
            "**Portfolio Diversification** — Assets with low or negative correlations provide "
            "diversification. When one falls, the other holds or rises. Traditional example: "
            "stocks (SPY) and bonds (TLT) are usually negatively correlated.\n\n"
            "**Regime Detection** — When normally uncorrelated assets suddenly move together "
            "(correlation spike), it signals a stress regime. In 2008 and March 2020, nearly "
            "everything correlated to ~1.0 (all falling together). High average correlation = risk.\n\n"
            "**Stock-Bond Correlation** — The key signal. When SPY-TLT correlation turns "
            "**positive** (both falling or both rising), it indicates an **inflation regime** "
            "where traditional 60/40 portfolios fail. Negative correlation = normal diversification works.\n\n"
            "**Safe Haven Shifts** — When bonds stop being a safe haven (positive stock-bond corr), "
            "look at Gold (GLD) or USD (UUP) as alternatives. Their correlation to stocks matters.\n\n"
            "**Pair Trading** — Highly correlated assets that diverge may revert. If two assets "
            "normally have 0.8+ correlation and one drops while the other doesn't, the divergence "
            "may close — either the laggard catches up or the leader falls back."
        )

    st.caption(
        f"Rolling {window}-day correlation matrix. "
        "Stock-bond correlation turning positive signals inflation regimes."
    )

    # Pair explorer — compute inline (not cached, since returns DF changes identity)
    st.markdown(
        f'<div style="font-size:15px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 4px 0;">'
        f'Pair Correlation Explorer</div>',
        unsafe_allow_html=True,
    )

    asset_names = list(matrix.columns)
    col1, col2 = st.columns(2)
    with col1:
        default_a1 = asset_names.index("S&P 500") if "S&P 500" in asset_names else 0
        a1 = st.selectbox("Asset 1", asset_names, index=default_a1, key="corr_a1")
    with col2:
        default_a2 = asset_names.index("Long Bonds") if "Long Bonds" in asset_names else min(3, len(asset_names) - 1)
        a2 = st.selectbox("Asset 2", asset_names, index=default_a2, key="corr_a2")

    st.caption(
        "Select two assets to see their rolling correlation over time. "
        "Watch for regime shifts — when correlation crosses zero, the relationship is changing."
    )

    if a1 == a2:
        st.info("Select two different assets.")
    elif a1 not in returns.columns or a2 not in returns.columns:
        st.warning(f"Data not available for {a1 if a1 not in returns.columns else a2}.")
    else:
        rolling_corr = returns[a1].rolling(window).corr(returns[a2])
        pair_df = pd.DataFrame({"Date": rolling_corr.index, "Correlation": rolling_corr.values}).dropna()

        if pair_df.empty:
            st.info("Not enough overlapping data for this pair.")
        elif len(pair_df) > 0:
            pair_line = (
                alt.Chart(pair_df)
                .mark_line(strokeWidth=1.5, color="#3D85C6")
                .encode(
                    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y-%m")),
                    y=alt.Y("Correlation:Q", title=f"{a1} vs {a2}",
                            scale=alt.Scale(domain=[-1, 1])),
                    tooltip=[alt.Tooltip("Correlation:Q", format=".2f"), "Date:T"],
                )
            )

            d_min, d_max = pair_df["Date"].min(), pair_df["Date"].max()
            ref_p = pd.DataFrame([{"Date": d_min, "Correlation": 0.5}, {"Date": d_max, "Correlation": 0.5}])
            ref_n = pd.DataFrame([{"Date": d_min, "Correlation": -0.5}, {"Date": d_max, "Correlation": -0.5}])
            ref_z = pd.DataFrame([{"Date": d_min, "Correlation": 0}, {"Date": d_max, "Correlation": 0}])

            rp = alt.Chart(ref_p).mark_line(strokeDash=[4, 4], strokeWidth=0.8, color=colors["green"]).encode(x="Date:T", y="Correlation:Q")
            rn = alt.Chart(ref_n).mark_line(strokeDash=[4, 4], strokeWidth=0.8, color=colors["red"]).encode(x="Date:T", y="Correlation:Q")
            rz = alt.Chart(ref_z).mark_line(strokeDash=[4, 4], strokeWidth=0.8, color=colors["text_muted"]).encode(x="Date:T", y="Correlation:Q")

            # Asset 1 price overlay on right axis
            a1_prices = returns[a1].loc[pair_df["Date"].min():pair_df["Date"].max()]
            a1_cumret = (1 + a1_prices).cumprod()
            a1_df = pd.DataFrame({"Date": a1_cumret.index, "Price": a1_cumret.values})

            a1_overlay = (
                alt.Chart(a1_df)
                .mark_line(strokeWidth=1, opacity=0.35, color=colors["green"])
                .encode(
                    x="Date:T",
                    y=alt.Y("Price:Q", title=a1, scale=alt.Scale(zero=False),
                            axis=alt.Axis(orient="right")),
                    tooltip=[alt.Tooltip("Price:Q", format=".2f"), "Date:T"],
                )
            )

            corr_layers = rn + rz + rp + pair_line
            chart = alt.layer(corr_layers, a1_overlay).resolve_scale(y="independent")

            st.altair_chart(
                _style_chart(chart, colors, 250),
                use_container_width=True,
            )

            current_corr = pair_df["Correlation"].iloc[-1]
            st.caption(
                f"Current {window}-day rolling correlation: **{current_corr:.2f}**. "
                f"Green line = {a1} cumulative return (right axis). "
                f"Dashed: green = +0.5, red = -0.5."
            )

    # Correlation regime backtester
    _render_corr_backtest(returns, colors, theme)


# ---------------------------------------------------------------------------
# Tab 4: Relative Strength Ranking
# ---------------------------------------------------------------------------

def _render_relative_strength_tab(colors: dict, theme: str):
    """Relative strength ranking with group selector, table, and RS line chart."""
    import numpy as np

    st.caption(
        "Relative strength ranks stocks by their outperformance vs a benchmark (SPY) across multiple timeframes. "
        "A positive RS means the stock is beating SPY; negative means lagging. The composite score weights "
        "1M (20%), 3M (30%), 6M (30%), 12M (20%)."
    )

    with st.expander("How Relative Strength Ranking Works"):
        st.markdown("""
**Relative Strength (RS)** measures how much an asset outperforms (or underperforms) a benchmark over a given period.

- **RS = Asset Return − Benchmark Return** (in percentage points)
- Example: If AAPL returned +15% in 3 months and SPY returned +8%, then RS(3M) = +7.0

**Composite RS** combines four timeframes with weights:
- **1M (20%)** — Recent momentum, responsive to news
- **3M (30%)** — Medium-term trend, most actionable
- **6M (30%)** — Established trend, less noise
- **12M (20%)** — Long-term leadership, catches secular winners

**How to use:**
- **Top RS stocks** are outperforming the market — consider for long positions or overweight
- **Bottom RS stocks** are underperforming — avoid, underweight, or consider for pairs trading
- **RS turning positive** from negative signals a momentum shift — potential entry point
- **RS turning negative** from positive signals deterioration — potential exit

**RS Line chart** shows the ratio of stock price to SPY price over time. Rising = outperforming.
The 13-week and 26-week moving averages smooth the signal — crossovers can indicate regime changes.
        """)

    # ---- Group Selector ----
    from services.technicals_data import _get_sp100_tickers
    group_options = _build_ac_group_options()
    group_options_rs = {"S&P 100 (default)": _get_sp100_tickers()}
    group_options_rs.update({k: v for k, v in group_options.items()})
    group_names = list(group_options_rs.keys())

    col_group, col_bench = st.columns([3, 1])
    with col_group:
        selected_group = st.selectbox(
            "Analyze tickers from",
            group_names,
            index=0,
            key="rs_group_select",
        )
    with col_bench:
        benchmark = st.selectbox("Benchmark", ["SPY", "QQQ", "IWM"], index=0, key="rs_benchmark")

    selected_tickers = group_options_rs[selected_group]
    if selected_tickers:
        custom_tuple = tuple(selected_tickers)
    else:
        custom_tuple = tuple(_get_sp100_tickers())

    with st.spinner("Computing relative strength rankings..."):
        data = fetch_rs_ranking(custom_tickers=custom_tuple, benchmark=benchmark)

    if not data:
        st.warning("Unable to compute RS data. Click 🔄 to refresh.")
        return

    df = data["table"]
    rs_lines = data["rs_lines"]

    # ---- Top 10 / Bottom 10 Bar Chart ----
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:12px 0 4px 0;">'
        f'Top & Bottom 10 by Composite RS vs {benchmark}</div>',
        unsafe_allow_html=True,
    )

    top10 = df.head(10).copy()
    bottom10 = df.tail(10).copy()
    bar_data = pd.concat([top10, bottom10])

    bar_chart = (
        alt.Chart(bar_data)
        .mark_bar()
        .encode(
            y=alt.Y("Ticker:N", sort=alt.SortField("Composite", order="descending"),
                     title=None, axis=alt.Axis(labelFontSize=11)),
            x=alt.X("Composite:Q", title="Composite RS (%)"),
            color=alt.condition(
                alt.datum.Composite > 0,
                alt.value(colors["green"]),
                alt.value(colors["red"]),
            ),
            tooltip=[
                "Ticker:N",
                alt.Tooltip("Composite:Q", format="+.1f", title="Composite RS"),
                alt.Tooltip("RS_1M:Q", format="+.1f", title="1M RS"),
                alt.Tooltip("RS_3M:Q", format="+.1f", title="3M RS"),
            ],
        )
        .properties(height=400)
    )

    bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
    styled = bar_chart.configure(
        background=bg_color,
    ).configure_axis(
        labelColor=colors["text_muted"],
        titleColor=colors["text_muted"],
        gridColor=f'{colors["text_muted"]}22',
    )
    st.altair_chart(styled, use_container_width=True)

    # ---- RS Table ----
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:16px 0 4px 0;">'
        f'Full Ranking ({len(df)} stocks)</div>',
        unsafe_allow_html=True,
    )

    # Build HTML table
    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:0.5;text-align:center">#</span>'
        '<span style="flex:1">Ticker</span>'
        '<span style="flex:1;text-align:right">1M RS</span>'
        '<span style="flex:1;text-align:right">3M RS</span>'
        '<span style="flex:1;text-align:right">6M RS</span>'
        '<span style="flex:1;text-align:right">12M RS</span>'
        '<span style="flex:1.2;text-align:right">Composite</span>'
        '</div>'
    )

    rows_html = []
    for _, row in df.iterrows():
        cells = []
        cells.append(f'<span style="flex:0.5;text-align:center;color:{colors["text_muted"]}">{int(row["Rank"])}</span>')
        cells.append(f'<span style="flex:1;font-weight:600">{row["Ticker"]}</span>')

        for col in ["RS_1M", "RS_3M", "RS_6M", "RS_12M", "Composite"]:
            val = row.get(col)
            if val is not None and not np.isnan(val):
                clr = colors["green"] if val > 0 else colors["red"] if val < 0 else colors["text_muted"]
                flex = "1.2" if col == "Composite" else "1"
                fw = "font-weight:600;" if col == "Composite" else ""
                cells.append(
                    f'<span style="flex:{flex};text-align:right;color:{clr};{fw}">{val:+.1f}</span>'
                )
            else:
                flex = "1.2" if col == "Composite" else "1"
                cells.append(f'<span style="flex:{flex};text-align:right;color:{colors["text_muted"]}">—</span>')

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{"".join(cells)}</div>'
        )

    # Show in scrollable container
    table_html = header + "".join(rows_html)
    st.markdown(
        f'<div style="max-height:400px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{table_html}</div>',
        unsafe_allow_html=True,
    )

    # ---- RS Line Chart for Selected Ticker ----
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Relative Strength Line</div>',
        unsafe_allow_html=True,
    )

    available_tickers = df["Ticker"].tolist()
    selected_ticker = st.selectbox(
        "Select ticker",
        available_tickers,
        index=0,
        key="rs_line_ticker",
    )

    if selected_ticker in rs_lines:
        rs_df = rs_lines[selected_ticker].dropna(subset=["RS_Line"]).tail(252)
        if not rs_df.empty:
            plot_df = rs_df.reset_index()

            rs_line = (
                alt.Chart(plot_df)
                .mark_line(strokeWidth=2, color="#3D85C6")
                .encode(
                    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %Y")),
                    y=alt.Y("RS_Line:Q", title=f"RS Line ({selected_ticker}/{benchmark})"),
                    tooltip=[alt.Tooltip("RS_Line:Q", format=".1f"), "Date:T"],
                )
            )

            layers = [rs_line]

            if "MA13" in plot_df.columns:
                ma13_data = plot_df.dropna(subset=["MA13"])
                if not ma13_data.empty:
                    ma13 = (
                        alt.Chart(ma13_data)
                        .mark_line(strokeWidth=1, strokeDash=[4, 3], color=colors["green"])
                        .encode(x="Date:T", y="MA13:Q")
                    )
                    layers.append(ma13)

            if "MA26" in plot_df.columns:
                ma26_data = plot_df.dropna(subset=["MA26"])
                if not ma26_data.empty:
                    ma26 = (
                        alt.Chart(ma26_data)
                        .mark_line(strokeWidth=1, strokeDash=[4, 3], color="#E8A838")
                        .encode(x="Date:T", y="MA26:Q")
                    )
                    layers.append(ma26)

            combined = layers[0]
            for layer in layers[1:]:
                combined = combined + layer

            styled = combined.properties(height=280).configure(
                background=bg_color,
            ).configure_axis(
                labelColor=colors["text_muted"],
                titleColor=colors["text_muted"],
                gridColor=f'{colors["text_muted"]}22',
            )
            st.altair_chart(styled, use_container_width=True)
            st.caption(
                f"Blue = RS line ({selected_ticker} price / {benchmark} price, normalized). "
                f"Green dashed = 13-week MA. Orange dashed = 26-week MA. "
                f"Rising RS line = outperforming {benchmark}."
            )
    else:
        st.caption(f"RS line chart not available for {selected_ticker}.")


# ---------------------------------------------------------------------------
# Tab 5: Weinstein Stage Analysis
# ---------------------------------------------------------------------------

def _render_stage_analysis_tab(colors: dict, theme: str):
    """Weinstein stage scanner — classify stocks into 4 stages."""
    import numpy as np

    st.caption(
        "Stan Weinstein's Stage Analysis classifies stocks into 4 lifecycle stages based on price relative to "
        "the 30-week moving average and its slope. Ideal for identifying Stage 2 breakouts (buy) and avoiding Stage 4 declines."
    )

    with st.expander("How Stage Analysis Works — Weinstein's 4 Stages"):
        st.markdown("""
**Stage 1 — Basing:** Price is below the 30-week MA, but the MA is flattening (no longer falling).
Volume is typically low and declining. The stock is building a base. *Watch for breakout.*

**Stage 2 — Advancing:** Price is above a rising 30-week MA. This is the **only stage to buy**.
Volume often expands on breakout. Momentum and trend-following strategies work best here.

**Stage 3 — Topping:** Price is still above the 30-week MA, but the MA is flattening or starting to turn down.
A warning sign — the trend is losing momentum. *Consider taking profits.*

**Stage 4 — Declining:** Price is below a falling 30-week MA. **Avoid or sell.**
Mean-reversion bounces are traps in Stage 4. Wait for Stage 1 basing before reconsidering.

**Practical rules:**
- Buy Stage 2 breakouts (price above rising 30-week MA with volume confirmation)
- Hold through Stage 2 as long as 30-week MA is rising
- Sell when Stage 3 is confirmed (MA flattening while price stalls)
- Never buy Stage 4 — "don't catch falling knives"
- Stage 1 basing patterns with tightening range are setup candidates

*Reference: Stan Weinstein, "Secrets for Profiting in Bull and Bear Markets" (1988)*
        """)

    # ---- Group Selector ----
    group_options = _build_ac_group_options()
    # Add S&P 100 as a dedicated option and make it default
    from services.technicals_data import _get_sp100_tickers
    group_options_stage = {"S&P 100 (default)": _get_sp100_tickers()}
    group_options_stage.update({k: v for k, v in group_options.items()})
    group_names = list(group_options_stage.keys())

    selected_group = st.selectbox(
        "Scan tickers from",
        group_names,
        index=0,
        key="stage_group_select",
    )

    selected_tickers = group_options_stage[selected_group]
    # Always pass tickers explicitly (never None)
    if selected_tickers:
        custom_tuple = tuple(selected_tickers)
    else:
        custom_tuple = tuple(_get_sp100_tickers())

    with st.spinner(f"Scanning {len(custom_tuple)} stocks for Weinstein stages (this may take 30-60s on first run)..."):
        data = fetch_stage_analysis(custom_tickers=custom_tuple)

    if not data:
        st.warning("Unable to run stage analysis. Click 🔄 to refresh.")
        return

    table = data["table"]
    distribution = data["distribution"]
    weekly_data = data["weekly_data"]
    total = data["total"]

    # ---- Stage Distribution KPI Cards ----
    kpi_cols = st.columns(4)
    for i, (stage_num, label) in enumerate(STAGE_LABELS.items()):
        count = distribution.get(stage_num, 0)
        pct = round(count / total * 100, 1) if total > 0 else 0
        clr = STAGE_COLORS[stage_num]
        short_label = label.split(" — ")[1]  # "Basing", "Advancing", etc.

        with kpi_cols[i]:
            st.markdown(
                f'<div style="border:1px solid {colors["border"]}44; border-radius:8px; '
                f'padding:12px; text-align:center; border-left:3px solid {clr};">'
                f'<div style="font-size:10px; text-transform:uppercase; color:{colors["text_muted"]}; '
                f'letter-spacing:0.5px;">Stage {stage_num} — {short_label}</div>'
                f'<div style="font-size:24px; font-weight:700; color:{clr};">{count}</div>'
                f'<div style="font-size:11px; color:{colors["text_muted"]};">{pct}% of {total}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ---- Stage Distribution Donut (Altair) ----
    # Build donut data with all 4 stages in fixed order for consistent colors
    all_stages = [1, 2, 3, 4]
    stage_names = [f"S{s} {STAGE_LABELS[s].split(' — ')[1]}" for s in all_stages]
    stage_colors = [STAGE_COLORS[s] for s in all_stages]
    stage_counts = [distribution.get(s, 0) for s in all_stages]

    donut_data = pd.DataFrame({
        "Stage": stage_names,
        "Count": stage_counts,
    })
    # Only show stages with count > 0 in the chart, but keep domain/range full for color consistency
    donut_visible = donut_data[donut_data["Count"] > 0]

    if not donut_visible.empty:
        donut = (
            alt.Chart(donut_visible)
            .mark_arc(innerRadius=50, outerRadius=90)
            .encode(
                theta=alt.Theta("Count:Q", stack=True),
                color=alt.Color(
                    "Stage:N",
                    scale=alt.Scale(
                        domain=stage_names,
                        range=stage_colors,
                    ),
                    legend=alt.Legend(orient="right", title=None),
                ),
                tooltip=["Stage:N", "Count:Q"],
            )
            .properties(height=220, width=300)
        )

        bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
        styled_donut = donut.configure(
            background=bg_color,
        ).configure_legend(
            labelColor=colors["text_muted"],
            labelFontSize=12,
        )
        st.altair_chart(styled_donut, use_container_width=False)

    # ---- Stage 2 Table (Advancing — the buy candidates) ----
    st.markdown("---")
    stage2 = table[table["Stage"] == 2].copy()
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{STAGE_COLORS[2]}; margin:8px 0 4px 0;">'
        f'Stage 2 — Advancing ({len(stage2)} stocks) — Buy Candidates</div>',
        unsafe_allow_html=True,
    )

    if not stage2.empty:
        _render_stage_table(stage2, colors)
    else:
        st.caption("No stocks currently in Stage 2.")

    # ---- Stage 4 Table (Declining — avoid) ----
    stage4 = table[table["Stage"] == 4].copy()
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{STAGE_COLORS[4]}; margin:12px 0 4px 0;">'
        f'Stage 4 — Declining ({len(stage4)} stocks) — Avoid</div>',
        unsafe_allow_html=True,
    )

    if not stage4.empty:
        _render_stage_table(stage4, colors)
    else:
        st.caption("No stocks currently in Stage 4.")

    # ---- Stage 1 & 3 in expanders ----
    stage1 = table[table["Stage"] == 1].copy()
    with st.expander(f"Stage 1 — Basing ({len(stage1)} stocks) — Watch for Breakout"):
        if not stage1.empty:
            _render_stage_table(stage1, colors)
        else:
            st.caption("No stocks currently in Stage 1.")

    stage3 = table[table["Stage"] == 3].copy()
    with st.expander(f"Stage 3 — Topping ({len(stage3)} stocks) — Consider Selling"):
        if not stage3.empty:
            _render_stage_table(stage3, colors)
        else:
            st.caption("No stocks currently in Stage 3.")

    # ---- Weekly Chart for Selected Ticker ----
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:14px; font-weight:600; color:{colors["text_header"]}; margin:8px 0 4px 0;">'
        f'Weekly Chart with 30-Week MA</div>',
        unsafe_allow_html=True,
    )

    available = [t for t in table["Ticker"].tolist() if t in weekly_data]
    if available:
        selected_ticker = st.selectbox("Select ticker", available, index=0, key="stage_chart_ticker")

        if selected_ticker in weekly_data:
            wk = weekly_data[selected_ticker].dropna(subset=["Close"]).tail(104)  # 2 years
            if not wk.empty:
                plot_df = wk.reset_index()

                # Price line
                price_line = (
                    alt.Chart(plot_df)
                    .mark_line(strokeWidth=2, color=colors["text"])
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %Y")),
                        y=alt.Y("Close:Q", title="Price ($)", scale=alt.Scale(zero=False)),
                        tooltip=[alt.Tooltip("Close:Q", format=",.2f"), "Date:T"],
                    )
                )

                layers = [price_line]

                # 30-week MA
                ma30_data = plot_df.dropna(subset=["MA30"])
                if not ma30_data.empty:
                    ma30_line = (
                        alt.Chart(ma30_data)
                        .mark_line(strokeWidth=1.5, color="#E8A838")
                        .encode(x="Date:T", y="MA30:Q")
                    )
                    layers.append(ma30_line)

                # 10-week MA
                ma10_data = plot_df.dropna(subset=["MA10"])
                if not ma10_data.empty:
                    ma10_line = (
                        alt.Chart(ma10_data)
                        .mark_line(strokeWidth=1, strokeDash=[4, 3], color="#6FA8DC")
                        .encode(x="Date:T", y="MA10:Q")
                    )
                    layers.append(ma10_line)

                combined = layers[0]
                for layer in layers[1:]:
                    combined = combined + layer

                # Get current stage for this ticker
                ticker_row = table[table["Ticker"] == selected_ticker]
                stage_label = ticker_row["Label"].iloc[0] if not ticker_row.empty else ""
                stage_num = ticker_row["Stage"].iloc[0] if not ticker_row.empty else 0
                stage_clr = STAGE_COLORS.get(stage_num, colors["text_muted"])

                bg_color = colors.get("chart_bg", "#0e1117" if theme == "dark" else "#ffffff")
                styled = combined.properties(height=300).configure(
                    background=bg_color,
                ).configure_axis(
                    labelColor=colors["text_muted"],
                    titleColor=colors["text_muted"],
                    gridColor=f'{colors["text_muted"]}22',
                )
                st.altair_chart(styled, use_container_width=True)
                st.markdown(
                    f'<div style="font-size:12px; color:{colors["text_muted"]};">'
                    f'Current classification: <span style="color:{stage_clr}; font-weight:600;">{stage_label}</span>. '
                    f'Orange = 30-week MA. Blue dashed = 10-week MA.</div>',
                    unsafe_allow_html=True,
                )


def _render_stage_table(df: pd.DataFrame, colors: dict):
    """Render a stage analysis table as HTML."""
    import numpy as np

    header = (
        '<div style="display:flex; padding:4px 8px; font-size:10px; text-transform:uppercase; '
        f'color:{colors["text_muted"]}; border-bottom:1px solid {colors["border"]}44;">'
        '<span style="flex:1">Ticker</span>'
        '<span style="flex:1;text-align:right">Price</span>'
        '<span style="flex:1;text-align:right">30W MA</span>'
        '<span style="flex:1.2;text-align:right">% from MA</span>'
        '<span style="flex:1;text-align:right">MA Slope</span>'
        '<span style="flex:0.8;text-align:center">Vol↑</span>'
        '</div>'
    )

    rows_html = []
    for _, row in df.iterrows():
        pct = row.get("Pct_from_MA30", 0)
        pct_clr = colors["green"] if pct > 0 else colors["red"]
        slope = row.get("MA30_Slope", 0)
        slope_clr = colors["green"] if slope > 0 else colors["red"]
        vol_icon = "✓" if row.get("Vol_Expanding") else "—"
        vol_clr = colors["green"] if row.get("Vol_Expanding") else colors["text_muted"]

        cells = (
            f'<span style="flex:1;font-weight:600">{row["Ticker"]}</span>'
            f'<span style="flex:1;text-align:right">${row["Price"]:,.2f}</span>'
            f'<span style="flex:1;text-align:right">${row["MA30"]:,.2f}</span>'
            f'<span style="flex:1.2;text-align:right;color:{pct_clr}">{pct:+.1f}%</span>'
            f'<span style="flex:1;text-align:right;color:{slope_clr}">{slope:+.2f}%</span>'
            f'<span style="flex:0.8;text-align:center;color:{vol_clr}">{vol_icon}</span>'
        )

        rows_html.append(
            f'<div style="display:flex; padding:3px 8px; font-size:12px; '
            f'border-bottom:1px solid {colors["border"]}22;">{cells}</div>'
        )

    table_html = header + "".join(rows_html)
    st.markdown(
        f'<div style="max-height:350px; overflow-y:auto; border:1px solid {colors["border"]}33; '
        f'border-radius:6px;">{table_html}</div>',
        unsafe_allow_html=True,
    )
