import os
from datetime import datetime, timezone

import streamlit as st

from services.config_manager import (
    save_config,
    add_strategy,
    remove_strategy,
    add_custom_group,
    remove_custom_group,
    update_custom_group_tickers,
    move_strategy,
    move_custom_group,
    add_screen,
    remove_screen,
    move_screen,
    add_ranking,
    remove_ranking,
    move_ranking,
    move_sidebar_order,
    add_trader_account,
    remove_trader_account,
    add_trader_strategy,
    remove_trader_strategy,
    move_trader_account,
    rename_trader_account,
    update_trader_strategy,
)
from services.p123_client import is_p123_configured, fetch_strategy_holdings, fetch_screen_holdings, fetch_ranking_holdings
from services.trader_notes import save_ranking_data, save_strategy_holdings, save_screen_holdings
from utils.indicators import INDICATOR_OPTIONS

# Pre-compute reverse lookup: indicator key → human label
_KEY_TO_LABEL = {v: k for k, v in INDICATOR_OPTIONS.items()}
_OPTIONS_LIST = list(INDICATOR_OPTIONS.keys())


def _rerun():
    """Rerun while keeping the settings dialog open."""
    st.session_state.show_settings = True
    st.rerun()


def _render_col_selectors(item: dict, config: dict, key_prefix: str,
                          col2_into=None, col3_into=None):
    """Render Col 2 / Col 3 indicator selectboxes for a group/strategy/screen.

    If *col2_into* / *col3_into* containers are provided the widgets are
    placed inside them (inline mode, labels collapsed).  Otherwise two new
    columns are created (legacy two-row mode).
    """
    inline = col2_into is not None
    if inline:
        cc1, cc2 = col2_into, col3_into
    else:
        cc1, cc2 = st.columns(2)
    label_vis = "collapsed" if inline else "visible"

    with cc1:
        cur_col2 = item.get("col2", "1M")
        cur_label2 = _KEY_TO_LABEL.get(cur_col2, "1 Month")
        idx2 = _OPTIONS_LIST.index(cur_label2) if cur_label2 in _OPTIONS_LIST else 0
        new_label2 = st.selectbox(
            "Col 2", options=_OPTIONS_LIST, index=idx2,
            key=f"col2_{key_prefix}", label_visibility=label_vis,
        )
        new_col2 = INDICATOR_OPTIONS[new_label2]
        if new_col2 != cur_col2:
            item["col2"] = new_col2
            save_config(config)
            st.session_state.config = config
            _rerun()
    with cc2:
        cur_col3 = item.get("col3", "3M")
        cur_label3 = _KEY_TO_LABEL.get(cur_col3, "3 Month")
        idx3 = _OPTIONS_LIST.index(cur_label3) if cur_label3 in _OPTIONS_LIST else 0
        new_label3 = st.selectbox(
            "Col 3", options=_OPTIONS_LIST, index=idx3,
            key=f"col3_{key_prefix}", label_visibility=label_vis,
        )
        new_col3 = INDICATOR_OPTIONS[new_label3]
        if new_col3 != cur_col3:
            item["col3"] = new_col3
            save_config(config)
            st.session_state.config = config
            _rerun()


@st.dialog("Settings", width="large")
def render_settings_dialog():
    config = st.session_state.config

    # Show API tab first when auto-opened due to missing credentials
    api_first = st.session_state.pop("settings_api_first", False)

    if api_first:
        tab3, tab1, tab1b, tab_rank, tab2, tab_order, tab4, tab_trader = st.tabs(
            ["API Settings", "P123 Strategies", "P123 Screens", "P123 Rankings",
             "Custom Groups", "Sidebar Order", "Data Settings", "Trader"]
        )
    else:
        tab1, tab1b, tab_rank, tab2, tab_order, tab3, tab4, tab_trader = st.tabs(
            ["P123 Strategies", "P123 Screens", "P123 Rankings", "Custom Groups",
             "Sidebar Order", "API Settings", "Data Settings", "Trader"]
        )

    # ---- P123 Strategies Tab ----
    with tab1:
        # Show API quota if available
        quota = st.session_state.get("p123_api_quota")
        if quota is not None:
            st.caption(f"API credits remaining: **{quota:,}**")

        strategies = config.get("strategies", [])
        if strategies:
            _sw = [2.5, 1.5, 1.5, 1.5, 0.5, 0.4, 0.4, 0.4, 1]
            hdr = st.columns(_sw)
            hdr[0].caption("Name")
            hdr[1].caption("ID")
            hdr[2].caption("Col 2")
            hdr[3].caption("Col 3")
            hdr[4].caption("News")
            for i, strat in enumerate(strategies):
                c_nm, c_id, c_c2, c_c3, c_nf, c_up, c_dn, c_ref, c_rm = st.columns(_sw)
                with c_nm:
                    st.text(strat["name"])
                with c_id:
                    st.caption(f"{strat['strategy_id']}")
                _render_col_selectors(strat, config, f"strat_{i}", c_c2, c_c3)
                with c_nf:
                    nf_val = strat.get("news_feed", True)
                    new_nf = st.checkbox("nf", value=nf_val, key=f"nf_strat_{i}",
                                         label_visibility="collapsed")
                    if new_nf != nf_val:
                        strat["news_feed"] = new_nf
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_up:
                    if st.button("▲", key=f"up_strat_{i}", disabled=i == 0, help="Move up"):
                        config = move_strategy(config, i, -1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_dn:
                    if st.button("▼", key=f"dn_strat_{i}", disabled=i == len(strategies) - 1, help="Move down"):
                        config = move_strategy(config, i, 1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_ref:
                    _do_refresh_strat = st.button("🔄", key=f"refresh_strat_{i}", type="secondary", help="Re-fetch holdings")
                if _do_refresh_strat:
                    with st.spinner(f"Fetching {strat['name']}..."):
                        holdings, api_quota = fetch_strategy_holdings(strat["strategy_id"])
                    strat_data = st.session_state.get("strategy_holdings", {})
                    strat_data[strat["strategy_id"]] = holdings
                    st.session_state.strategy_holdings = strat_data
                    now = datetime.now(timezone.utc)
                    st.session_state.strategy_holdings_update = now
                    save_strategy_holdings(strat_data, now)
                    st.cache_data.clear()
                    if api_quota is not None:
                        st.session_state.p123_api_quota = api_quota
                    _rerun()
                with c_rm:
                    if st.button("Remove", key=f"rm_strat_{i}", type="secondary"):
                        # Remove persisted holdings
                        strat_data = st.session_state.get("strategy_holdings", {})
                        strat_data.pop(strat["strategy_id"], None)
                        st.session_state.strategy_holdings = strat_data
                        save_strategy_holdings(strat_data, st.session_state.get("strategy_holdings_update"))
                        config = remove_strategy(config, strat["strategy_id"])
                        save_config(config)
                        st.session_state.config = config
                        st.cache_data.clear()
                        _rerun()
        else:
            st.info("No strategies configured yet.")

        st.markdown("---")
        st.markdown("**Add New Strategy**")
        col_name, col_id = st.columns(2)
        with col_name:
            new_name = st.text_input("Strategy Name", key="new_strat_name", placeholder="e.g. Growth Portfolio")
        with col_id:
            new_id = st.number_input("Strategy ID", min_value=1, step=1, key="new_strat_id", value=None)

        if st.button("Add Strategy", type="primary", disabled=not (new_name and new_id)):
            config = add_strategy(config, new_name, int(new_id))
            save_config(config)
            st.session_state.config = config
            st.cache_data.clear()
            _rerun()

    # ---- P123 Screens Tab ----
    with tab1b:
        # Show API quota if available
        quota = st.session_state.get("p123_api_quota")
        if quota is not None:
            st.caption(f"API credits remaining: **{quota:,}**")

        screens = config.get("screens", [])
        if screens:
            _scw = [2, 1, 0.8, 1.3, 1.3, 0.5, 0.4, 0.4, 0.4, 1]
            hdr = st.columns(_scw)
            hdr[0].caption("Name")
            hdr[1].caption("ID")
            hdr[2].caption("Max")
            hdr[3].caption("Col 2")
            hdr[4].caption("Col 3")
            hdr[5].caption("News")
            for i, scr in enumerate(screens):
                c_nm, c_id, c_mx, c_c2, c_c3, c_nf, c_up, c_dn, c_ref, c_rm = st.columns(_scw)
                with c_nm:
                    st.text(scr["name"])
                with c_id:
                    st.caption(f"{scr['screen_id']}")
                with c_mx:
                    st.caption(f"{scr.get('max_holdings', 50)}")
                _render_col_selectors(scr, config, f"scr_{i}", c_c2, c_c3)
                with c_nf:
                    nf_val = scr.get("news_feed", True)
                    new_nf = st.checkbox("nf", value=nf_val, key=f"nf_scr_{i}",
                                         label_visibility="collapsed")
                    if new_nf != nf_val:
                        scr["news_feed"] = new_nf
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_up:
                    if st.button("▲", key=f"up_scr_{i}", disabled=i == 0, help="Move up"):
                        config = move_screen(config, i, -1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_dn:
                    if st.button("▼", key=f"dn_scr_{i}", disabled=i == len(screens) - 1, help="Move down"):
                        config = move_screen(config, i, 1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_ref:
                    _do_refresh_scr = st.button("🔄", key=f"refresh_scr_{i}", type="secondary", help="Re-fetch screen")
                if _do_refresh_scr:
                    with st.spinner(f"Fetching {scr['name']}..."):
                        holdings, api_quota = fetch_screen_holdings(
                            scr["screen_id"], scr.get("max_holdings", 50)
                        )
                    scr_data = st.session_state.get("screen_holdings", {})
                    scr_data[scr["screen_id"]] = holdings
                    st.session_state.screen_holdings = scr_data
                    now = datetime.now(timezone.utc)
                    st.session_state.screen_holdings_update = now
                    save_screen_holdings(scr_data, now)
                    st.cache_data.clear()
                    if api_quota is not None:
                        st.session_state.p123_api_quota = api_quota
                    _rerun()
                with c_rm:
                    if st.button("Remove", key=f"rm_scr_{i}", type="secondary"):
                        # Remove persisted holdings
                        scr_data = st.session_state.get("screen_holdings", {})
                        scr_data.pop(scr["screen_id"], None)
                        st.session_state.screen_holdings = scr_data
                        save_screen_holdings(scr_data, st.session_state.get("screen_holdings_update"))
                        config = remove_screen(config, scr["screen_id"])
                        save_config(config)
                        st.session_state.config = config
                        st.cache_data.clear()
                        _rerun()
        else:
            st.info("No screens configured yet.")

        st.markdown("---")
        st.markdown("**Add New Screen**")
        col_name, col_id, col_max = st.columns(3)
        with col_name:
            scr_name = st.text_input("Screen Name", key="new_scr_name", placeholder="e.g. Value Screen")
        with col_id:
            scr_id = st.number_input("Screen ID", min_value=1, step=1, key="new_scr_id", value=None)
        with col_max:
            scr_max = st.number_input("Max Holdings", min_value=1, max_value=500, step=1, key="new_scr_max", value=50)

        if st.button("Add Screen", type="primary", disabled=not (scr_name and scr_id)):
            config = add_screen(config, scr_name, int(scr_id), int(scr_max))
            save_config(config)
            st.session_state.config = config
            st.cache_data.clear()
            _rerun()

    # ---- P123 Rankings Tab ----
    with tab_rank:
        # Show API quota if available
        quota = st.session_state.get("p123_api_quota")
        if quota is not None:
            st.caption(f"API credits remaining: **{quota:,}**")

        rankings = config.get("rankings", [])
        if rankings:
            _rw = [1.8, 0.8, 1.8, 0.6, 1.2, 1.2, 0.4, 0.4, 0.4, 0.4, 0.8]
            hdr = st.columns(_rw)
            hdr[0].caption("Name")
            hdr[1].caption("ID")
            hdr[2].caption("Universe")
            hdr[3].caption("Max")
            hdr[4].caption("Col 2")
            hdr[5].caption("Col 3")
            hdr[6].caption("News")
            for i, rnk in enumerate(rankings):
                c_nm, c_id, c_uni, c_mx, c_c2, c_c3, c_nf, c_up, c_dn, c_ref, c_rm = st.columns(_rw)
                with c_nm:
                    st.text(rnk["name"])
                with c_id:
                    st.caption(f"{rnk['ranking_id']}")
                with c_uni:
                    st.caption(rnk.get("universe", ""))
                with c_mx:
                    st.caption(f"{rnk.get('max_holdings', 25)}")
                _render_col_selectors(rnk, config, f"rank_{i}", c_c2, c_c3)
                with c_nf:
                    nf_val = rnk.get("news_feed", True)
                    new_nf = st.checkbox("nf", value=nf_val, key=f"nf_rank_{i}",
                                         label_visibility="collapsed")
                    if new_nf != nf_val:
                        rnk["news_feed"] = new_nf
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_up:
                    if st.button("▲", key=f"up_rank_{i}", disabled=i == 0, help="Move up"):
                        config = move_ranking(config, i, -1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_dn:
                    if st.button("▼", key=f"dn_rank_{i}", disabled=i == len(rankings) - 1, help="Move down"):
                        config = move_ranking(config, i, 1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_ref:
                    _do_refresh_rank = st.button("🔄", key=f"refresh_rank_{i}", type="secondary", help="Refresh ranking")
                if _do_refresh_rank:
                    with st.spinner(f"Fetching {rnk['name']}..."):
                        holdings, nodes_data, api_quota = fetch_ranking_holdings(
                            rnk["ranking_id"],
                            rnk.get("universe", "Easy to Trade US"),
                        )
                    if holdings:
                        ranking_data = st.session_state.get("ranking_data", {})
                        ranking_data[rnk["ranking_id"]] = holdings
                        st.session_state.ranking_data = ranking_data
                        ranking_nodes = st.session_state.get("ranking_nodes", {})
                        if nodes_data:
                            ranking_nodes[rnk["ranking_id"]] = nodes_data
                        st.session_state.ranking_nodes = ranking_nodes
                        now = datetime.now(timezone.utc)
                        st.session_state.ranking_last_update = now
                        save_ranking_data(ranking_data, ranking_nodes, now)
                        st.cache_data.clear()
                        if api_quota is not None:
                            st.session_state.p123_api_quota = api_quota
                    _rerun()
                with c_rm:
                    if st.button("Remove", key=f"rm_rank_{i}", type="secondary"):
                        # Remove from ranking_data and nodes
                        ranking_data = st.session_state.get("ranking_data", {})
                        ranking_data.pop(rnk["ranking_id"], None)
                        st.session_state.ranking_data = ranking_data
                        ranking_nodes = st.session_state.get("ranking_nodes", {})
                        ranking_nodes.pop(rnk["ranking_id"], None)
                        st.session_state.ranking_nodes = ranking_nodes
                        save_ranking_data(
                            ranking_data, ranking_nodes,
                            st.session_state.get("ranking_last_update"),
                        )
                        config = remove_ranking(config, rnk["ranking_id"])
                        save_config(config)
                        st.session_state.config = config
                        st.cache_data.clear()
                        _rerun()
        else:
            st.info("No rankings configured yet.")

        st.markdown("---")
        st.markdown("**Add New Ranking**")
        col_rname, col_rid = st.columns(2)
        with col_rname:
            rank_name = st.text_input("Ranking Name", key="new_rank_name",
                                       placeholder="e.g. Small Micro Cap Focus")
        with col_rid:
            rank_id = st.number_input("Ranking System ID", min_value=1, step=1,
                                       key="new_rank_id", value=None)
        col_runi, col_rmax = st.columns(2)
        with col_runi:
            rank_universe = st.text_input("Universe", key="new_rank_universe",
                                           placeholder="e.g. Easy to Trade US")
        with col_rmax:
            rank_max = st.number_input("Max Holdings", min_value=1, max_value=500,
                                        step=1, key="new_rank_max", value=25)

        if st.button("Add Ranking", type="primary",
                      disabled=not (rank_name and rank_id and rank_universe)):
            config = add_ranking(config, rank_name, int(rank_id),
                                  rank_universe, int(rank_max))
            save_config(config)
            st.session_state.config = config
            _rerun()

    # ---- Custom Groups Tab ----
    with tab2:
        groups = config.get("custom_groups", [])
        if groups:
            _gw = [1.5, 2.5, 1.3, 1.3, 0.5, 0.4, 0.4, 1]
            hdr = st.columns(_gw)
            hdr[0].caption("Name")
            hdr[1].caption("Tickers")
            hdr[2].caption("Col 2")
            hdr[3].caption("Col 3")
            hdr[4].caption("News")
            for i, group in enumerate(groups):
                c_nm, c_tk, c_c2, c_c3, c_nf, c_up, c_dn, c_rm = st.columns(_gw)
                with c_nm:
                    st.text(group["name"])
                with c_tk:
                    new_tickers_str = st.text_input(
                        "Tickers",
                        value=", ".join(group.get("tickers", [])),
                        key=f"edit_group_{i}",
                        label_visibility="collapsed",
                    )
                    new_tickers = [
                        t.strip().upper() for t in new_tickers_str.split(",") if t.strip()
                    ]
                    if new_tickers != group.get("tickers", []):
                        config = update_custom_group_tickers(config, group["name"], new_tickers)
                        save_config(config)
                        st.session_state.config = config
                _render_col_selectors(group, config, f"group_{i}", c_c2, c_c3)
                with c_nf:
                    nf_val = group.get("news_feed", True)
                    new_nf = st.checkbox("nf", value=nf_val, key=f"nf_group_{i}",
                                         label_visibility="collapsed")
                    if new_nf != nf_val:
                        group["news_feed"] = new_nf
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_up:
                    if st.button("▲", key=f"up_group_{i}", disabled=i == 0, help="Move up"):
                        config = move_custom_group(config, i, -1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_dn:
                    if st.button("▼", key=f"dn_group_{i}", disabled=i == len(groups) - 1, help="Move down"):
                        config = move_custom_group(config, i, 1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with c_rm:
                    if st.button("Remove", key=f"rm_group_{i}", type="secondary"):
                        config = remove_custom_group(config, group["name"])
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
        else:
            st.info("No custom groups yet.")

        st.markdown("---")
        st.markdown("**Add New Group**")
        col_gname, col_gtickers = st.columns(2)
        with col_gname:
            group_name = st.text_input("Group Name", key="new_group_name", placeholder="e.g. FAANG")
        with col_gtickers:
            group_tickers_str = st.text_input(
                "Tickers (comma-separated)",
                key="new_group_tickers",
                placeholder="AAPL, MSFT, GOOGL",
            )

        if st.button("Add Group", type="primary", disabled=not (group_name and group_tickers_str)):
            tickers = [t.strip().upper() for t in group_tickers_str.split(",") if t.strip()]
            config = add_custom_group(config, group_name, tickers)
            save_config(config)
            st.session_state.config = config
            _rerun()

    # ---- Sidebar Order Tab ----
    with tab_order:
        st.markdown("**Sidebar Group Order**")
        st.caption("Reorder how groups appear in the sidebar using ▲ / ▼.")
        order = config.get("sidebar_order", [])

        _TYPE_ICONS = {"custom": "📋", "strategy": "📊", "screen": "🔍", "ranking": "🏆"}
        _TYPE_LABELS = {"custom": "", "strategy": "Strat: ", "screen": "Scr: ", "ranking": "Rank: "}

        if order:
            for i, entry in enumerate(order):
                etype = entry.get("type", "custom")
                ename = entry.get("name", "?")
                icon = _TYPE_ICONS.get(etype, "")
                prefix = _TYPE_LABELS.get(etype, "")
                col_icon, col_name, col_up, col_dn = st.columns([0.5, 5, 0.5, 0.5])
                with col_icon:
                    st.markdown(icon)
                with col_name:
                    st.text(f"{prefix}{ename}")
                with col_up:
                    if st.button("▲", key=f"up_order_{i}", disabled=i == 0, help="Move up"):
                        config = move_sidebar_order(config, i, -1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with col_dn:
                    if st.button("▼", key=f"dn_order_{i}", disabled=i == len(order) - 1, help="Move down"):
                        config = move_sidebar_order(config, i, 1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
        else:
            st.info("No groups to order yet. Add groups in the other tabs first.")

    # ---- API Settings Tab ----
    with tab3:
        st.markdown("**Portfolio123 API Connection**")
        if is_p123_configured():
            st.success("P123 API: Credentials configured")
        else:
            st.warning("P123 API: Not configured")

        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

        # Read current values from .env (display only, not the env vars)
        current_id = ""
        current_key = ""
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("P123_API_ID"):
                        current_id = line.split("=", 1)[1].strip()
                    elif line.startswith("P123_API_KEY"):
                        current_key = line.split("=", 1)[1].strip()

        new_api_id = st.text_input(
            "API ID",
            value=current_id,
            key="p123_api_id_input",
            placeholder="Your P123 API ID",
        )
        new_api_key = st.text_input(
            "API Key",
            value=current_key,
            key="p123_api_key_input",
            placeholder="Your P123 API Key",
        )

        if st.button("Save API Credentials", type="primary"):
            with open(env_path, "w") as f:
                f.write(f"P123_API_ID={new_api_id.strip()}\n")
                f.write(f"P123_API_KEY={new_api_key.strip()}\n")
            st.success("Saved! Restart the app to apply new credentials.")
            os.environ["P123_API_ID"] = new_api_id.strip()
            os.environ["P123_API_KEY"] = new_api_key.strip()

    # ---- Data Settings Tab ----
    with tab4:
        settings = config.setdefault("settings", {})

        # -- Market Overview Tickers --
        st.markdown("**Market Overview Tickers**")
        st.caption("Customize which tickers appear in the top overview bar (max 8). Use Yahoo Finance symbols (e.g. ^GSPC, ^NDX, ^VIX, GC=F, BTC-USD).")

        current_overview = settings.get("overview_tickers", ["^GSPC", "^NDX", "^RUT", "^N100", "^N225", "^VIX", "GC=F"])
        overview_str = st.text_input(
            "Tickers (comma-separated)",
            value=", ".join(current_overview),
            key="overview_tickers_input",
            placeholder="^GSPC, ^NDX, ^RUT, ^N100, ^N225, ^VIX, GC=F",
        )
        new_overview = [t.strip() for t in overview_str.split(",") if t.strip()][:8]
        if new_overview != current_overview:
            settings["overview_tickers"] = new_overview
            save_config(config)
            st.session_state.config = config
            st.cache_data.clear()
            _rerun()

        st.markdown("---")

        # -- Top Movers Count --
        st.markdown("**Top Gainers / Losers**")
        st.caption("Number of top gainers and losers to display.")

        current_movers = settings.get("movers_count", 5)
        new_movers = st.number_input(
            "Number of movers",
            min_value=1,
            max_value=20,
            step=1,
            value=current_movers,
            key="movers_count_input",
        )
        if new_movers != current_movers:
            settings["movers_count"] = int(new_movers)
            save_config(config)
            st.session_state.config = config
            _rerun()

        st.markdown("---")

        # -- Forum Post Count --
        st.markdown("**Community Forum**")
        st.caption("Number of latest forum posts to display.")

        current_forum = settings.get("forum_post_count", 4)
        new_forum = st.number_input(
            "Number of forum posts",
            min_value=1,
            max_value=20,
            step=1,
            value=current_forum,
            key="forum_post_count_input",
        )
        if new_forum != current_forum:
            settings["forum_post_count"] = int(new_forum)
            save_config(config)
            st.session_state.config = config
            _rerun()

        st.markdown("---")

        # -- Sparkline Timeframe --
        st.markdown("**Sparkline Chart Period**")
        st.caption("Timeframe for the mini charts in the overview cards.")

        sparkline_options = {
            "Intraday (1 day)": "1d",
            "5 days": "5d",
            "1 month": "1mo",
            "3 months": "3mo",
            "1 year": "1y",
        }
        current_spark = settings.get("sparkline_period", "5d")

        current_spark_label = "5 days"
        for label, val in sparkline_options.items():
            if val == current_spark:
                current_spark_label = label
                break

        selected_spark = st.selectbox(
            "Sparkline period",
            options=list(sparkline_options.keys()),
            index=list(sparkline_options.keys()).index(current_spark_label),
            key="sparkline_period_select",
        )
        new_spark = sparkline_options[selected_spark]

        if new_spark != current_spark:
            settings["sparkline_period"] = new_spark
            save_config(config)
            st.session_state.config = config
            st.cache_data.clear()
            _rerun()

        st.markdown("---")

        # -- Auto-Refresh --
        st.markdown("**Auto-Refresh**")
        st.caption("How often market data refreshes automatically. Yahoo Finance has rate limits, so keep intervals reasonable (5+ minutes).")

        refresh_options = {
            "Off": 0,
            "5 minutes": 5,
            "10 minutes": 10,
            "15 minutes": 15,
            "30 minutes": 30,
            "60 minutes": 60,
        }
        current_interval = settings.get("refresh_interval_minutes", 0)

        current_label = "Off"
        for label, val in refresh_options.items():
            if val == current_interval:
                current_label = label
                break

        selected_label = st.selectbox(
            "Refresh interval",
            options=list(refresh_options.keys()),
            index=list(refresh_options.keys()).index(current_label),
            key="refresh_interval_select",
        )
        new_interval = refresh_options[selected_label]

        if new_interval != current_interval:
            settings["refresh_interval_minutes"] = new_interval
            save_config(config)
            st.session_state.config = config
            _rerun()

        st.markdown("---")

        # -- Grok AI Analysis --
        st.markdown("**Grok AI Analysis**")
        st.caption(
            "Question template sent to Grok when you click the ✦ icon on a ticker. "
            "Use `{ticker}` as a placeholder for the stock symbol."
        )

        from services.config_manager import _DEFAULT_GROK_TEMPLATE
        current_grok = settings.get("grok_question_template", _DEFAULT_GROK_TEMPLATE)

        new_grok = st.text_area(
            "Question template",
            value=current_grok,
            height=200,
            key="grok_template_input",
        )

        if new_grok != current_grok:
            settings["grok_question_template"] = new_grok
            save_config(config)
            st.session_state.config = config
            _rerun()

    # ---- Trader Tab ----
    with tab_trader:
        st.markdown("**Trader Accounts**")
        st.caption("Configure accounts and strategies for the Strategy Trader 123 panel.")

        accounts = config.get("trader_accounts", [])

        if accounts:
            for i, account in enumerate(accounts):
                # Account header row — editable name
                ca_name, ca_up, ca_dn, ca_rm = st.columns([4, 0.4, 0.4, 1])
                with ca_name:
                    new_acct = st.text_input(
                        "Account", value=account["name"],
                        key=f"edit_tacct_{i}", label_visibility="collapsed",
                    )
                    if new_acct.strip() and new_acct != account["name"]:
                        config = rename_trader_account(config, account["name"], new_acct.strip())
                        save_config(config)
                        st.session_state.config = config
                with ca_up:
                    if st.button("▲", key=f"up_tacct_{i}", disabled=i == 0, help="Move up"):
                        config = move_trader_account(config, i, -1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with ca_dn:
                    if st.button("▼", key=f"dn_tacct_{i}",
                                  disabled=i == len(accounts) - 1, help="Move down"):
                        config = move_trader_account(config, i, 1)
                        save_config(config)
                        st.session_state.config = config
                        _rerun()
                with ca_rm:
                    if st.button("Remove", key=f"rm_tacct_{i}", type="secondary"):
                        config = remove_trader_account(config, account["name"])
                        save_config(config)
                        st.session_state.config = config
                        _rerun()

                # Strategies within this account — editable name & ID
                for j, strat in enumerate(account.get("strategies", [])):
                    cs_name, cs_id, cs_rm = st.columns([3, 1.5, 1])
                    with cs_name:
                        new_sname = st.text_input(
                            "Name", value=strat["name"],
                            key=f"edit_tstrat_name_{i}_{j}",
                            label_visibility="collapsed",
                        )
                    with cs_id:
                        new_sid = st.number_input(
                            "ID", value=strat["id"], min_value=1, step=1,
                            key=f"edit_tstrat_id_{i}_{j}",
                            label_visibility="collapsed",
                        )
                    # Auto-save on change
                    if new_sname != strat["name"] or int(new_sid) != strat["id"]:
                        config = update_trader_strategy(
                            config, account["name"], strat["id"],
                            int(new_sid), new_sname,
                        )
                        save_config(config)
                        st.session_state.config = config
                    with cs_rm:
                        if st.button("Remove", key=f"rm_tstrat_{i}_{j}", type="secondary"):
                            config = remove_trader_strategy(
                                config, account["name"], strat["id"]
                            )
                            save_config(config)
                            st.session_state.config = config
                            _rerun()

                # Add strategy to this account
                with st.expander(f"Add strategy to {account['name']}", expanded=False):
                    ts_name = st.text_input(
                        "Strategy Name", key=f"new_tstrat_name_{i}",
                        placeholder="e.g. AI 2000 Secret Sauce",
                    )
                    ts_id = st.number_input(
                        "Strategy ID", min_value=1, step=1,
                        key=f"new_tstrat_id_{i}", value=None,
                    )
                    if st.button("Add Strategy", key=f"add_tstrat_{i}",
                                  type="primary", disabled=not (ts_name and ts_id)):
                        config = add_trader_strategy(
                            config, account["name"], int(ts_id), ts_name
                        )
                        save_config(config)
                        st.session_state.config = config
                        _rerun()

                st.markdown("---")
        else:
            st.info("No trader accounts configured yet.")

        # Add new account form
        st.markdown("**Add New Account**")
        new_acct_name = st.text_input(
            "Account Name", key="new_tacct_name",
            placeholder="e.g. QP Fundamenta",
        )
        if st.button("Add Account", type="primary", disabled=not new_acct_name):
            config = add_trader_account(config, new_acct_name)
            save_config(config)
            st.session_state.config = config
            _rerun()
