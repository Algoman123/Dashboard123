import time
import streamlit as st
from services.config_manager import load_config
from services.market_data import fetch_market_data, format_pct, format_volume
from components.sidebar import render_sidebar
from components.chart import render_tradingview_chart
from components.market_overview import render_market_overview
from components.gainers_losers import render_gainers_losers
from components.forum_posts import render_forum_posts
from components.news import render_ticker_news
from components.settings_dialog import render_settings_dialog
from components.trader_panel import render_trader_panel
from components.news_feed import render_news_feed
from utils.theme import get_theme_css
from utils.constants import DEFAULT_TICKER, TICKER_DISPLAY_NAMES, COLORS_DARK, COLORS_LIGHT
from services.p123_client import is_p123_configured
from services.trader_notes import (
    load_notes, load_trader_data, load_ranking_data,
    load_strategy_holdings, load_screen_holdings,
)
from utils.p123_icon import GROK_SVG, X_SVG, STOCKTWITS_SVG
from components.radar_chart import generate_radar_svg, get_top_level_indices
import base64


def init_session_state():
    """Initialize session state with defaults."""
    if "config" not in st.session_state:
        st.session_state.config = load_config()

    config = st.session_state.config

    if "selected_ticker" not in st.session_state:
        st.session_state.selected_ticker = config.get("settings", {}).get(
            "default_ticker", DEFAULT_TICKER
        )
    if "theme" not in st.session_state:
        st.session_state.theme = config.get("settings", {}).get("theme", "dark")
    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False

    # Right panel state: 0=off, 1=trader, 2=news feed
    if "right_panel_mode" not in st.session_state:
        st.session_state.right_panel_mode = 0
    if "trader_data" not in st.session_state:
        saved_data, saved_update = load_trader_data()
        st.session_state.trader_data = saved_data
        st.session_state.trader_last_update = saved_update
    if "trader_notes" not in st.session_state:
        st.session_state.trader_notes = load_notes()
    if "trader_last_update" not in st.session_state:
        st.session_state.trader_last_update = None
    if "trader_commit_results" not in st.session_state:
        st.session_state.trader_commit_results = []
    if "trader_fetch_results" not in st.session_state:
        st.session_state.trader_fetch_results = []

    # P123 holdings (persisted to disk, manually refreshed)
    if "strategy_holdings" not in st.session_state:
        saved_strat, saved_strat_update = load_strategy_holdings()
        st.session_state.strategy_holdings = saved_strat
        st.session_state.strategy_holdings_update = saved_strat_update
    if "screen_holdings" not in st.session_state:
        saved_scr, saved_scr_update = load_screen_holdings()
        st.session_state.screen_holdings = saved_scr
        st.session_state.screen_holdings_update = saved_scr_update
    if "ranking_data" not in st.session_state:
        saved_rankings, saved_nodes, saved_ranking_update = load_ranking_data()
        st.session_state.ranking_data = saved_rankings
        st.session_state.ranking_nodes = saved_nodes
        st.session_state.ranking_last_update = saved_ranking_update

    # Auto-open settings to API tab if P123 not configured (once per session)
    if not is_p123_configured() and "api_settings_prompted" not in st.session_state:
        st.session_state.show_settings = True
        st.session_state.settings_api_first = True
        st.session_state.api_settings_prompted = True


def render_detail_panel(ticker: str, colors: dict):
    """Render the selected ticker's full performance breakdown."""
    data = fetch_market_data((ticker,))
    if data.empty or ticker not in data.index:
        return

    row = data.loc[ticker]
    display_name = TICKER_DISPLAY_NAMES.get(ticker, ticker)
    price = row.get("Price", 0)
    daily = row.get("Daily")
    _, daily_cls = format_pct(daily)

    # Price formatting
    price_str = f"{price:,.2f}" if price < 10000 else f"{price:,.0f}"
    daily_str, _ = format_pct(daily)

    # Build metric cards for all periods
    metrics = [
        ("Daily", row.get("Daily")),
        ("5 Day", row.get("5D")),
        ("1 Month", row.get("1M")),
        ("3 Month", row.get("3M")),
        ("1 Year", row.get("1Y")),
    ]

    vol_str = format_volume(row.get("Volume"))

    # Build metric HTML items
    metric_cells = []
    for label, val in metrics:
        val_str, cls = format_pct(val)
        metric_cells.append(
            f'<div style="text-align:center;">'
            f'<div style="font-size:10px;color:{colors["text_muted"]};text-transform:uppercase;letter-spacing:0.3px;">{label}</div>'
            f'<div class="{cls}" style="font-size:14px;font-weight:600;">{val_str}</div>'
            f'</div>'
        )
    metric_cells.append(
        f'<div style="text-align:center;">'
        f'<div style="font-size:10px;color:{colors["text_muted"]};text-transform:uppercase;letter-spacing:0.3px;">Volume</div>'
        f'<div style="font-size:14px;font-weight:600;color:{colors["text"]};">{vol_str}</div>'
        f'</div>'
    )

    # Grok AI analysis link
    import urllib.parse
    grok_template = st.session_state.get("config", {}).get("settings", {}).get(
        "grok_question_template", ""
    )
    if grok_template and not ticker.startswith("^"):
        grok_q = urllib.parse.quote(
            grok_template.replace("{ticker}", ticker)
        )
        grok_svg_lg = GROK_SVG.replace(
            'width="14" height="14"', 'width="40" height="40"'
        )
        grok_html = (
            f'<a href="https://grok.com/?q={grok_q}" target="_blank" '
            f'class="grok-link" '
            f'title="Analyze {ticker} with Grok" '
            f'style="margin-left:10px;width:40px;height:40px;'
            f'color:{colors["text_muted"]};vertical-align:middle;">'
            f'{grok_svg_lg}</a>'
        )
    else:
        grok_html = ''

    # X (Twitter) cashtag search link
    if not ticker.startswith("^"):
        # Strip exchange suffix (.TO, .V, .ST etc.) for cashtag
        cashtag = ticker.split(".")[0] if "." in ticker else ticker
        x_svg_lg = X_SVG.replace(
            'width="14" height="14"', 'width="28" height="28"'
        )
        x_html = (
            f'<a href="https://x.com/search?q=%24{urllib.parse.quote(cashtag)}"'
            f' target="_blank" class="grok-link"'
            f' title="Search ${cashtag} on X"'
            f' style="margin-left:6px;width:28px;height:28px;'
            f'color:{colors["text_muted"]};vertical-align:middle;">'
            f'{x_svg_lg}</a>'
        )
        # StockTwits link
        st_svg_lg = STOCKTWITS_SVG.replace(
            'width="14" height="14"', 'width="28" height="28"'
        )
        st_html = (
            f'<a href="https://stocktwits.com/symbol/{urllib.parse.quote(cashtag)}"'
            f' target="_blank" class="grok-link"'
            f' title="View {cashtag} on StockTwits"'
            f' style="margin-left:6px;width:28px;height:28px;'
            f'color:{colors["text_muted"]};vertical-align:middle;">'
            f'{st_svg_lg}</a>'
        )
    else:
        x_html = ''
        st_html = ''

    # Single-row detail panel: name | metrics | price
    st.markdown(
        f"""<div class="detail-panel" style="display:flex;align-items:center;gap:20px;">
            <div style="flex-shrink:0;display:flex;align-items:center;">
                <span class="ticker-name">{display_name}</span>
                <span style="color:{colors['text_muted']};font-size:13px;margin-left:6px;">{ticker}</span>
                {grok_html}{x_html}{st_html}
            </div>
            <div style="display:flex;gap:16px;flex:1;justify-content:center;">
                {"".join(metric_cells)}
            </div>
            <div style="flex-shrink:0;text-align:right;">
                <div style="font-size:10px;color:{colors['text_muted']};text-transform:uppercase;letter-spacing:0.3px;">Price</div>
                <div style="font-size:18px;font-weight:700;color:{colors['text']};">{price_str}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ---- Membership info (strategies, screens, rankings) ----
    config = st.session_state.config
    badges = []

    for strat in config.get("strategies", []):
        sid = strat["strategy_id"]
        holdings = st.session_state.get("strategy_holdings", {}).get(sid, [])
        if ticker in holdings:
            badges.append(
                f'<span class="membership-badge">📊 Strat: {strat["name"]}</span>'
            )

    for scr in config.get("screens", []):
        sid = scr["screen_id"]
        holdings = st.session_state.get("screen_holdings", {}).get(sid, [])
        if ticker in holdings:
            badges.append(
                f'<span class="membership-badge">🔍 Scr: {scr["name"]}</span>'
            )

    ranking_update = st.session_state.get("ranking_last_update")
    date_str = (
        f"{ranking_update.strftime('%b')} {ranking_update.day}"
        if ranking_update
        else ""
    )
    for rank_cfg in config.get("rankings", []):
        rid = rank_cfg["ranking_id"]
        holdings = st.session_state.get("ranking_data", {}).get(rid, [])
        if ticker in holdings:
            pos = holdings.index(ticker) + 1
            total = len(holdings)
            pct = (1 - pos / total) * 100 if total else 0
            uni = rank_cfg.get("universe", "")
            info = f'🏆 Rank: {rank_cfg["name"]} (#{pos}/{total} · {pct:.2f}%'
            if uni:
                info += f" · {uni}"
            if date_str:
                info += f" · {date_str}"
            info += ")"
            badges.append(f'<span class="membership-badge">{info}</span>')

    if badges:
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:2px;'
            'margin-bottom:2px;">' + "".join(badges) + "</div>",
            unsafe_allow_html=True,
        )


def _render_ranking_radars(ticker: str, colors: dict):
    """Render radar charts for any ranking systems that contain the ticker."""
    config = st.session_state.config
    ranking_nodes = st.session_state.get("ranking_nodes", {})
    if not ranking_nodes:
        return

    charts = []
    for rank_cfg in config.get("rankings", []):
        rid = rank_cfg["ranking_id"]
        ndata = ranking_nodes.get(rid)
        if not ndata:
            continue
        scores = ndata.get("scores", {})
        if ticker not in scores:
            continue

        # Top-level nodes: direct children of the root (Overall)
        top_indices = get_top_level_indices(
            ndata.get("ids", []), ndata.get("parents", []),
            total=len(ndata["names"]),
        )

        # Filter to top-level nodes only
        all_names = ndata["names"]
        all_weights = ndata["weights"]
        ticker_scores = scores[ticker]

        top_names = [all_names[i] for i in top_indices]
        top_values = [ticker_scores[i] for i in top_indices]
        top_weights = [all_weights[i] for i in top_indices]

        svg = generate_radar_svg(
            title=rank_cfg["name"],
            categories=top_names,
            values=top_values,
            weights=top_weights,
            colors=colors,
            chart_id=f"radar_{rid}",
        )
        if svg:
            charts.append(svg)

    if not charts:
        return

    # Render radar charts side by side (up to 3 per row)
    # Encode SVG as base64 <img> to bypass Streamlit's HTML sanitizer
    cols = st.columns(min(len(charts), 3))
    for i, svg in enumerate(charts):
        with cols[i % 3]:
            b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
            st.markdown(
                f'<img src="data:image/svg+xml;base64,{b64}" '
                f'style="width:100%;max-width:540px;display:block;margin:0 auto;">',
                unsafe_allow_html=True,
            )


def _render_main_content(selected: str, colors: dict, theme: str):
    """Render all main dashboard content (overview, movers, detail, chart)."""
    render_market_overview()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    col_movers, col_forum = st.columns([1, 1])
    with col_movers:
        render_gainers_losers()
    with col_forum:
        render_forum_posts()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    render_detail_panel(selected, colors)

    _render_ranking_radars(selected, colors)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    render_tradingview_chart(selected, theme)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    render_ticker_news(selected, colors)


def main():
    st.set_page_config(
        page_title="Dashboard123",
        page_icon="chart_with_upwards_trend",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    # Handle ticker selection via URL query params (from movers/trader/news HTML links)
    if "select" in st.query_params:
        st.session_state.selected_ticker = st.query_params["select"]
        # tv=1 flag means the click came from the trader panel — keep it open
        if "tv" in st.query_params:
            st.session_state.right_panel_mode = 1
        # nf=1 flag means the click came from the news feed — keep it open
        elif "nf" in st.query_params:
            st.session_state.right_panel_mode = 2
        st.query_params.clear()

    theme = st.session_state.theme
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # Inject theme CSS
    st.markdown(get_theme_css(theme), unsafe_allow_html=True)

    # Auto-refresh: clear cache and rerun on interval
    refresh_minutes = st.session_state.config.get("settings", {}).get("refresh_interval_minutes", 0)
    if refresh_minutes > 0:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = time.time()
        elapsed = time.time() - st.session_state.last_refresh
        if elapsed >= refresh_minutes * 60:
            st.session_state.last_refresh = time.time()
            st.cache_data.clear()
            st.rerun()

    # Settings dialog
    if st.session_state.get("show_settings"):
        st.session_state.show_settings = False
        render_settings_dialog()

    # Sidebar
    with st.sidebar:
        render_sidebar()

    # Main area — optionally split with right panel (trader or news feed)
    selected = st.session_state.selected_ticker
    panel_mode = st.session_state.get("right_panel_mode", 0)

    if panel_mode == 1:  # Trader panel
        col_main, col_right = st.columns([7, 3])
        with col_main:
            _render_main_content(selected, colors, theme)
        with col_right:
            render_trader_panel()
    elif panel_mode == 2:  # News feed
        col_main, col_right = st.columns([7, 3])
        with col_main:
            _render_main_content(selected, colors, theme)
        with col_right:
            render_news_feed()
    else:
        # Full width — render directly to avoid CSS scope leak
        _render_main_content(selected, colors, theme)


if __name__ == "__main__":
    main()
