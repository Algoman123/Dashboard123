import pandas as pd
import streamlit as st
from services.market_data import fetch_market_data
from services.config_manager import save_config
from services.p123_client import p123_stock_url
from utils.constants import TICKER_DISPLAY_NAMES, COLORS_DARK, COLORS_LIGHT
from utils.p123_icon import P123_WAVE_SVG as _P123_WAVE_SVG
from utils.indicators import INDICATORS, format_indicator


def collect_all_tickers(config: dict) -> set[str]:
    """Gather all unique tickers from all groups."""
    tickers = set()
    for group in config.get("custom_groups", []):
        tickers.update(group.get("tickers", []))
    # Include persisted P123 holdings (strategies, screens, rankings)
    for sid, holdings in st.session_state.get("strategy_holdings", {}).items():
        tickers.update(holdings)
    for sid, holdings in st.session_state.get("screen_holdings", {}).items():
        tickers.update(holdings)
    # Only include display tickers (top max_holdings) — not the full reference list
    ranking_limits = {
        r["ranking_id"]: r.get("max_holdings", 25)
        for r in config.get("rankings", [])
    }
    for rid, holdings in st.session_state.get("ranking_data", {}).items():
        limit = ranking_limits.get(rid, 25)
        tickers.update(holdings[:limit])
    return tickers


def _render_ticker_table(tickers, market_data, group_key, colors,
                         col2_key="1M", col3_key="3M"):
    """Render clickable ticker table with performance data (3 data columns)."""
    selected = st.session_state.get("selected_ticker", "")

    col2_header = INDICATORS.get(col2_key, {}).get("header", col2_key)
    col3_header = INDICATORS.get(col3_key, {}).get("header", col3_key)

    # Column header
    st.markdown(
        f'<div class="ticker-col-header">'
        f'<span style="flex:0.3"></span>'
        f'<span style="flex:3.2">Ticker</span>'
        f'<span style="flex:1.5;text-align:right">Day</span>'
        f'<span style="flex:1.5;text-align:right">{col2_header}</span>'
        f'<span style="flex:1.5;text-align:right">{col3_header}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    for ticker in tickers:
        row = None
        if not market_data.empty and ticker in market_data.index:
            row = market_data.loc[ticker]

        display_name = TICKER_DISPLAY_NAMES.get(ticker, ticker)

        # Daily (always first data column)
        daily_val = row.get("Daily") if row is not None else None
        daily_str, daily_color = format_indicator("Daily", daily_val, colors)

        # Col 2 (per-group configurable)
        col2_val = row.get(col2_key) if row is not None else None
        col2_str, col2_color = format_indicator(col2_key, col2_val, colors)

        # Col 3 (per-group configurable)
        col3_val = row.get(col3_key) if row is not None else None
        col3_str, col3_color = format_indicator(col3_key, col3_val, colors)

        name_short = display_name[:8] if display_name != ticker else ""
        btn_label = f"{ticker:<6}{name_short}" if name_short else ticker

        p123_link = p123_stock_url(ticker)

        c0, c1, c2, c3, c4 = st.columns([0.3, 3.2, 1.5, 1.5, 1.5])
        with c0:
            if p123_link:
                st.markdown(
                    f'<a href="{p123_link}" target="_blank" class="p123-link" '
                    f'title="Open {ticker} on P123">{_P123_WAVE_SVG}</a>',
                    unsafe_allow_html=True,
                )
        with c1:
            if st.button(
                btn_label,
                key=f"btn_{group_key}_{ticker}",
                use_container_width=True,
            ):
                st.session_state.selected_ticker = ticker
                st.rerun()
        with c2:
            st.markdown(
                f'<div class="pct-cell" style="color:{daily_color}">{daily_str}</div>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<div class="pct-cell" style="color:{col2_color}">{col2_str}</div>',
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f'<div class="pct-cell" style="color:{col3_color}">{col3_str}</div>',
                unsafe_allow_html=True,
            )


def render_ticker_group(group_name, tickers, market_data, colors, expanded=True,
                        col2_key="1M", col3_key="3M"):
    """Render a collapsible ticker group."""
    # Compute average daily % for the group header
    avg_label = ""
    if not market_data.empty and tickers:
        valid = [t for t in tickers if t in market_data.index]
        if valid:
            avg = market_data.loc[valid, "Daily"].mean()
            if pd.notna(avg):
                arrow = "▲" if avg > 0 else "▼" if avg < 0 else "–"
                avg_label = f"  {arrow} {avg:+.2f}%"

    with st.expander(f"{group_name}{avg_label}", expanded=expanded):
        _render_ticker_table(tickers, market_data, group_name, colors,
                             col2_key=col2_key, col3_key=col3_key)


def _get_group_cols(config, group_type, group_name):
    """Look up col2/col3 from a group's config entry."""
    if group_type == "custom":
        collection = config.get("custom_groups", [])
    elif group_type == "strategy":
        collection = config.get("strategies", [])
    elif group_type == "screen":
        collection = config.get("screens", [])
    elif group_type == "ranking":
        collection = config.get("rankings", [])
    else:
        return "1M", "3M"
    for g in collection:
        if g.get("name") == group_name:
            return g.get("col2", "1M"), g.get("col3", "3M")
    return "1M", "3M"


def render_sidebar():
    """Main sidebar rendering function."""
    config = st.session_state.config
    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # ---- Header (SVG logo) ----
    logo_color = colors["text_header"]
    _f = "'Nunito Sans',system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    st.markdown(
        f'<svg viewBox="0 -6 380 80" xmlns="http://www.w3.org/2000/svg"'
        f' style="width:100%;max-width:280px;height:auto;margin-bottom:-2px;">'
        # "Dashboard" bold text
        f'<text x="0" y="55" font-family="{_f}"'
        f' font-size="48" font-weight="700" letter-spacing="-1" fill="{logo_color}">Dashboard</text>'
        # "1" near baseline
        f'<text x="278" y="62" font-family="{_f}"'
        f' font-size="20" font-weight="400" fill="{logo_color}">1</text>'
        # Wavy ascending line 1→2 (dip, tilde wave at bottom, sharp rise)
        f'<path d="M 289 58 C 293 68,297 72,300 68 C 302 65,300 68,304 60'
        f' C 310 44,318 36,322 34"'
        f' stroke="{logo_color}" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        # "2" mid-level
        f'<text x="322" y="36" font-family="{_f}"'
        f' font-size="20" font-weight="400" fill="{logo_color}">2</text>'
        # Wavy ascending line 2→3 (same pattern)
        f'<path d="M 335 32 C 339 42,343 46,346 42 C 348 39,346 42,350 34'
        f' C 356 18,364 10,368 8"'
        f' stroke="{logo_color}" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        # "3" at top
        f'<text x="366" y="12" font-family="{_f}"'
        f' font-size="20" font-weight="400" fill="{logo_color}">3</text>'
        f'</svg>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        theme_icon = "☀️" if theme == "dark" else "🌙"
        if st.button(theme_icon, key="theme_toggle", use_container_width=True, help="Toggle theme"):
            new_theme = "light" if theme == "dark" else "dark"
            st.session_state.theme = new_theme
            config["settings"]["theme"] = new_theme
            save_config(config)
            st.rerun()
    with c2:
        if st.button("⚙️", key="settings_btn", use_container_width=True, help="Settings"):
            st.session_state.show_settings = True
            st.rerun()
    with c3:
        if st.button("🔄", key="refresh_btn", use_container_width=True, help="Refresh data"):
            st.cache_data.clear()
            st.rerun()
    with c4:
        mode = st.session_state.get("right_panel_mode", 0)
        _icons = ["📈", "📰", "✖️"]
        _helps = ["Open Trader", "Switch to News", "Close Panel"]
        if st.button(
            _icons[mode],
            key="panel_toggle_btn",
            use_container_width=True,
            help=_helps[mode],
        ):
            st.session_state.right_panel_mode = (mode + 1) % 3
            st.rerun()

    st.markdown("---")

    # ---- Collect tickers and fetch market data ----
    all_tickers = collect_all_tickers(config)

    # Strategy holdings (loaded from session state, persisted to disk)
    p123_holdings = {}
    for strategy in config.get("strategies", []):
        sid = strategy["strategy_id"]
        tickers_list = st.session_state.get("strategy_holdings", {}).get(sid, [])
        p123_holdings[strategy["name"]] = tickers_list
        all_tickers.update(tickers_list)

    # Screen holdings (loaded from session state, persisted to disk)
    p123_screens = {}
    for screen in config.get("screens", []):
        sid = screen["screen_id"]
        tickers_list = st.session_state.get("screen_holdings", {}).get(sid, [])
        p123_screens[screen["name"]] = tickers_list
        all_tickers.update(tickers_list)

    # Ranking holdings — slice to max_holdings for display; full list stays
    # in session state for membership-badge rank lookups.
    p123_rankings = {}
    for ranking in config.get("rankings", []):
        rid = ranking["ranking_id"]
        full_list = st.session_state.get("ranking_data", {}).get(rid, [])
        display_list = full_list[:ranking.get("max_holdings", 25)]
        p123_rankings[ranking["name"]] = display_list
        all_tickers.update(display_list)

    # Single batch download for all tickers
    if all_tickers:
        with st.spinner("Loading market data..."):
            market_data = fetch_market_data(tuple(sorted(all_tickers)))
    else:
        market_data = pd.DataFrame()

    # Share with main area (for gainers/losers component)
    st.session_state.market_data = market_data

    # Build news feed ticker set (only groups with news_feed enabled)
    nf_tickers: set[str] = set()
    for group in config.get("custom_groups", []):
        if group.get("news_feed", True):
            nf_tickers.update(group.get("tickers", []))
    for strategy in config.get("strategies", []):
        if strategy.get("news_feed", True):
            nf_tickers.update(p123_holdings.get(strategy["name"], []))
    for screen in config.get("screens", []):
        if screen.get("news_feed", True):
            nf_tickers.update(p123_screens.get(screen["name"], []))
    for ranking in config.get("rankings", []):
        if ranking.get("news_feed", True):
            nf_tickers.update(p123_rankings.get(ranking["name"], []))
    st.session_state.news_feed_tickers = nf_tickers

    # ---- Build lookup maps ----
    custom_map = {g["name"]: g.get("tickers", []) for g in config.get("custom_groups", [])}
    strategy_map = {s["name"]: s for s in config.get("strategies", [])}
    screen_map = {s["name"]: s for s in config.get("screens", [])}
    ranking_map = {r["name"]: r for r in config.get("rankings", [])}

    # ---- Render groups in sidebar_order ----
    sidebar_order = config.get("sidebar_order", [])
    rendered = set()

    # Default expand: first two groups expanded, rest collapsed
    for idx, entry in enumerate(sidebar_order):
        etype = entry.get("type")
        ename = entry.get("name")
        key = (etype, ename)
        if key in rendered:
            continue
        rendered.add(key)
        expanded = idx < 2
        col2, col3 = _get_group_cols(config, etype, ename)

        if etype == "custom":
            tickers = custom_map.get(ename, [])
            if tickers:
                render_ticker_group(ename, tickers, market_data, colors,
                                    expanded=expanded, col2_key=col2, col3_key=col3)

        elif etype == "strategy":
            tickers = p123_holdings.get(ename, [])
            if tickers:
                render_ticker_group(f"Strat: {ename}", tickers, market_data, colors,
                                    expanded=expanded, col2_key=col2, col3_key=col3)
            elif ename in strategy_map:
                with st.expander(f"Strat: {ename}", expanded=False):
                    st.caption("No holdings loaded. Check API credentials and strategy ID.")

        elif etype == "screen":
            tickers = p123_screens.get(ename, [])
            if tickers:
                render_ticker_group(f"Scr: {ename}", tickers, market_data, colors,
                                    expanded=expanded, col2_key=col2, col3_key=col3)
            elif ename in screen_map:
                with st.expander(f"Scr: {ename}", expanded=False):
                    st.caption("No holdings loaded. Check API credentials and screen ID.")

        elif etype == "ranking":
            tickers = p123_rankings.get(ename, [])
            if tickers:
                render_ticker_group(f"Rank: {ename}", tickers, market_data, colors,
                                    expanded=expanded, col2_key=col2, col3_key=col3)
            elif ename in ranking_map:
                with st.expander(f"Rank: {ename}", expanded=False):
                    st.caption("No holdings loaded. Refresh rankings in Settings.")

    # ---- Render any groups not yet in sidebar_order (safety net) ----
    for name, tickers in custom_map.items():
        if ("custom", name) not in rendered and tickers:
            col2, col3 = _get_group_cols(config, "custom", name)
            render_ticker_group(name, tickers, market_data, colors, expanded=False,
                                col2_key=col2, col3_key=col3)

    for strategy in config.get("strategies", []):
        name = strategy["name"]
        if ("strategy", name) not in rendered:
            tickers = p123_holdings.get(name, [])
            if tickers:
                col2, col3 = _get_group_cols(config, "strategy", name)
                render_ticker_group(f"Strat: {name}", tickers, market_data, colors,
                                    expanded=False, col2_key=col2, col3_key=col3)

    for screen in config.get("screens", []):
        name = screen["name"]
        if ("screen", name) not in rendered:
            tickers = p123_screens.get(name, [])
            if tickers:
                col2, col3 = _get_group_cols(config, "screen", name)
                render_ticker_group(f"Scr: {name}", tickers, market_data, colors,
                                    expanded=False, col2_key=col2, col3_key=col3)

    for ranking in config.get("rankings", []):
        name = ranking["name"]
        if ("ranking", name) not in rendered:
            tickers = p123_rankings.get(name, [])
            if tickers:
                col2, col3 = _get_group_cols(config, "ranking", name)
                render_ticker_group(f"Rank: {name}", tickers, market_data, colors,
                                    expanded=False, col2_key=col2, col3_key=col3)

    # ---- Buy Me a Coffee link ----
    st.markdown(
        '<div style="text-align:center;padding:16px 0 8px;">'
        '<a href="https://buymeacoffee.com/algoman" target="_blank" '
        'style="color:#888;text-decoration:none;font-size:12px;">'
        '☕ Buy me a coffee</a></div>',
        unsafe_allow_html=True,
    )
