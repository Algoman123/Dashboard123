"""Strategy Trader 123 -- right-side panel for rebalance workflow."""

import urllib.parse
from datetime import datetime, timezone

import streamlit as st

from services.p123_client import fetch_rebalance_recs, commit_rebalance, p123_stock_url, _p123_to_yfinance
from services.trader_notes import save_notes, set_note, get_noted_tickers, save_trader_data
from utils.constants import COLORS_DARK, COLORS_LIGHT
from utils.p123_icon import P123_WAVE_SVG, GROK_SVG


# ---- Internal helpers ----


def _fetch_all_recommendations():
    """Fetch rebalance recs for all configured trader strategies."""
    config = st.session_state.config
    accounts = config.get("trader_accounts", [])
    trader_data: dict = {}
    last_quota = None
    fetch_results: list[str] = []

    for account in accounts:
        account_name = account["name"]
        for strategy in account["strategies"]:
            sid = strategy["id"]
            strategy_name = strategy["name"]
            try:
                recs = fetch_rebalance_recs(sid)

                # Build rank lookup
                rank_dict = {uid: rank for uid, rank in recs.get("ranks", [])}
                processed = []
                for rec in recs.get("recs", []):
                    rank = round(rank_dict.get(rec.get("p123Uid"), 0.0), 2)
                    processed.append({
                        "rec": rec.copy(),
                        "rank": rank,
                        "is_dummy": False,
                    })

                # Add dummy HOLD entries for noted tickers not in current recs
                notes = st.session_state.get("trader_notes", {})
                current_tickers = {r["rec"]["ticker"] for r in processed}
                for ticker in get_noted_tickers(notes, sid):
                    if ticker not in current_tickers:
                        processed.append({
                            "rec": {"ticker": ticker, "action": "HOLD", "shares": 0},
                            "rank": 0.0,
                            "is_dummy": True,
                        })

                trader_data[sid] = {
                    "ranks": recs.get("ranks", []),
                    "op": recs.get("op"),
                    "recs": processed,
                    "name": strategy_name,
                    "account": account_name,
                }

                rec_count = len(processed)
                fetch_results.append(
                    f"{strategy_name}: {rec_count} rec(s)"
                )

                if isinstance(recs, dict) and "quotaRemaining" in recs:
                    last_quota = recs["quotaRemaining"]

            except Exception as e:
                fetch_results.append(f"Error: {strategy_name} — {e}")

    # Clear stale widget state so new API values take effect
    # (Streamlit widget state overrides the value= parameter if the key exists)
    stale_keys = [k for k in st.session_state
                  if k.startswith(("shares_t_", "chk_t_"))]
    for k in stale_keys:
        del st.session_state[k]

    st.session_state.trader_data = trader_data
    st.session_state.trader_last_update = datetime.now(timezone.utc)
    st.session_state.trader_fetch_results = fetch_results
    if last_quota is not None:
        st.session_state.p123_api_quota = last_quota
    # Persist to disk so data survives session restarts
    save_trader_data(trader_data, st.session_state.trader_last_update)


def _commit_selected():
    """Commit checked rebalance transactions."""
    trader_data = st.session_state.get("trader_data", {})
    results = []
    to_remove: dict[int, list[int]] = {}

    for sid, sdata in trader_data.items():
        checked_indices = []
        for idx in range(len(sdata["recs"])):
            ticker_key = sdata["recs"][idx]["rec"].get("ticker", str(idx))
            if st.session_state.get(f"chk_t_{sid}_{ticker_key}", False):
                checked_indices.append(idx)

        if not checked_indices:
            continue

        normal = [i for i in checked_indices if not sdata["recs"][i].get("is_dummy")]
        dummy = [i for i in checked_indices if sdata["recs"][i].get("is_dummy")]
        to_remove.setdefault(sid, []).extend(dummy)

        # Build transaction list from normal (non-dummy) recs
        trans = []
        for i in normal:
            try:
                tk = sdata["recs"][i]["rec"].get("ticker", str(i))
                shares = int(st.session_state.get(f"shares_t_{sid}_{tk}", 0))
                sdata["recs"][i]["rec"]["shares"] = shares
            except (ValueError, TypeError):
                ticker = sdata["recs"][i]["rec"].get("ticker", "?")
                results.append(f"Error: Invalid shares for {ticker}")
                continue
            trans.append(sdata["recs"][i]["rec"])

        if trans:
            try:
                resp = commit_rebalance(
                    strategy_id=sid,
                    ranks=sdata["ranks"],
                    trans=trans,
                    op=sdata.get("op"),
                )
                results.append(f"Committed {len(trans)} trade(s) for {sdata['name']}")
                if isinstance(resp, dict) and "quotaRemaining" in resp:
                    st.session_state.p123_api_quota = resp["quotaRemaining"]
                to_remove.setdefault(sid, []).extend(normal)
            except Exception as e:
                results.append(f"Error committing {sdata['name']}: {e}")

    # Remove committed / dummy recs and clean up notes
    notes = st.session_state.get("trader_notes", {})
    for sid, indices in to_remove.items():
        for i in sorted(indices, reverse=True):
            if i < len(trader_data[sid]["recs"]):
                ticker = trader_data[sid]["recs"][i]["rec"]["ticker"]
                notes.pop((sid, ticker), None)
                del trader_data[sid]["recs"][i]
    save_notes(notes)
    st.session_state.trader_notes = notes
    st.session_state.trader_data = trader_data
    st.session_state.trader_commit_results = results
    # Persist updated data to disk
    save_trader_data(trader_data, st.session_state.get("trader_last_update"))


# ---- Public render function ----


def render_trader_panel():
    """Render the Strategy Trader 123 right-side panel."""
    config = st.session_state.config
    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT
    accounts = config.get("trader_accounts", [])

    # Trader panel marker for CSS scoping
    st.markdown('<div class="trader-panel-marker"></div>', unsafe_allow_html=True)

    # Title
    st.markdown("#### Strategy Trader 123")

    if not accounts:
        st.info("No trader accounts configured. Add accounts in **Settings > Trader**.")
        return

    # Header: last update + fetch button
    h1, h2 = st.columns([2, 1])
    with h1:
        if st.session_state.trader_last_update:
            ts = st.session_state.trader_last_update
            st.caption(f"Updated: {ts.strftime('%H:%M:%S UTC')}")
        else:
            st.caption("Not yet loaded")
    with h2:
        if st.button("Fetch Recs", key="trader_fetch_btn", type="primary",
                      use_container_width=True):
            with st.spinner("Fetching..."):
                _fetch_all_recommendations()
            st.rerun()

    # Show fetch results (persisted across rerun)
    for msg in st.session_state.get("trader_fetch_results", []):
        if msg.startswith("Error"):
            st.error(msg)
        else:
            st.caption(msg)
    st.session_state.trader_fetch_results = []

    # Show commit results (persisted across rerun)
    for msg in st.session_state.get("trader_commit_results", []):
        if msg.startswith("Error"):
            st.error(msg)
        else:
            st.success(msg)
    st.session_state.trader_commit_results = []

    # Quota
    quota = st.session_state.get("p123_api_quota")
    if quota is not None:
        st.caption(f"API credits: **{quota:,}**")

    trader_data = st.session_state.get("trader_data", {})
    if not trader_data:
        st.caption("Press **Fetch Recs** to load recommendations.")
        return

    # Group strategies by account
    account_groups: dict[str, list] = {}
    for sid, sdata in trader_data.items():
        account_groups.setdefault(sdata["account"], []).append((sid, sdata))

    # Render per account
    for account in accounts:
        account_name = account["name"]
        strategies_in_account = account_groups.get(account_name, [])
        if not strategies_in_account:
            continue

        # Collect all recs for this account
        all_rows = []
        for sid, sdata in strategies_in_account:
            for idx, srec in enumerate(sdata["recs"]):
                all_rows.append({
                    **srec,
                    "strategy_id": sid,
                    "rec_index": idx,
                    "strategy_name": sdata["name"],
                })

        if not all_rows:
            continue

        # Sort: BUY → HOLD → SELL
        _order = {"BUY": 0, "HOLD": 1, "SELL": 2}
        all_rows.sort(key=lambda x: _order.get(x["rec"].get("action", ""), 3))

        # Account header
        st.markdown(f"**{account_name}**")

        # Column header labels (use same st.columns proportions as data rows)
        hdr_style = f"font-size:10px;color:{colors['text_muted']};text-transform:uppercase;letter-spacing:0.3px;"
        h_chk, h_act, h_strat, h_tick, h_rank, h_shares, h_note = st.columns(
            [0.3, 0.5, 1.5, 1.2, 0.5, 0.7, 1.5]
        )
        with h_chk:
            st.markdown(f'<span style="{hdr_style}">&nbsp;</span>', unsafe_allow_html=True)
        with h_act:
            st.markdown(f'<span style="{hdr_style}">Act</span>', unsafe_allow_html=True)
        with h_strat:
            st.markdown(f'<span style="{hdr_style}">Strategy</span>', unsafe_allow_html=True)
        with h_tick:
            st.markdown(f'<span style="{hdr_style}">Ticker</span>', unsafe_allow_html=True)
        with h_rank:
            st.markdown(f'<span style="{hdr_style}">Rank</span>', unsafe_allow_html=True)
        with h_shares:
            st.markdown(f'<span style="{hdr_style}">Shares</span>', unsafe_allow_html=True)
        with h_note:
            st.markdown(f'<span style="{hdr_style}">Note</span>', unsafe_allow_html=True)

        prev_action = None
        for row in all_rows:
            rec = row["rec"]
            action = rec.get("action", "")
            sid = row["strategy_id"]
            rec_idx = row["rec_index"]
            # Use ticker-based keys so widget state follows the ticker,
            # not the positional index (which can change on re-fetch)
            ticker_key = rec.get("ticker", str(rec_idx))
            kp = f"t_{sid}_{ticker_key}"

            # Separator before SELL section
            if prev_action in ("BUY", "HOLD") and action == "SELL":
                st.markdown(
                    f'<hr style="border:none;border-top:1px dashed '
                    f'{colors["red"]}66;margin:2px 0;">',
                    unsafe_allow_html=True,
                )

            # Row columns: chk | action | strategy | ticker | rank | shares | note
            c_chk, c_act, c_strat, c_tick, c_rank, c_shares, c_note = st.columns(
                [0.3, 0.5, 1.5, 1.2, 0.5, 0.7, 1.5]
            )

            with c_chk:
                st.checkbox("s", key=f"chk_{kp}", label_visibility="collapsed")

            with c_act:
                if action == "BUY":
                    act_color = colors["green"]
                elif action == "SELL":
                    act_color = colors["red"]
                else:
                    act_color = colors["text_muted"]
                st.markdown(
                    f'<span style="color:{act_color};font-weight:700;'
                    f'font-size:12px;">{action}</span>',
                    unsafe_allow_html=True,
                )

            with c_strat:
                url = f"https://www.portfolio123.com/port_summary.jsp?portid={sid}"
                st.markdown(
                    f'<a href="{url}" target="_blank" style="color:{colors["text_muted"]};'
                    f'text-decoration:none;font-size:11px;">{row["strategy_name"]}</a>',
                    unsafe_allow_html=True,
                )

            with c_tick:
                ticker = rec.get("ticker", "")
                # Convert P123 format (AAPL:USA) to yfinance (AAPL) for links/display
                yf_ticker = _p123_to_yfinance(ticker)
                display_ticker = yf_ticker
                # P123 stock page link (needs yfinance format)
                p123_link = p123_stock_url(yf_ticker)
                p123_icon = (
                    f'<a href="{p123_link}" target="_blank" class="p123-link" '
                    f'title="Open {display_ticker} on P123">{P123_WAVE_SVG}</a>'
                    if p123_link
                    else ''
                )
                # Grok AI analysis link
                grok_template = config.get("settings", {}).get(
                    "grok_question_template", ""
                )
                if grok_template:
                    grok_q = urllib.parse.quote(
                        grok_template.replace("{ticker}", display_ticker)
                    )
                    grok_icon = (
                        f'<a href="https://grok.com/?q={grok_q}" target="_blank" '
                        f'class="grok-link" '
                        f'title="Analyze {display_ticker} with Grok">{GROK_SVG}</a>'
                    )
                else:
                    grok_icon = ''
                # Chart selection link (needs yfinance format)
                # tv=1 flag preserves trader panel visibility across navigation
                # target=_self prevents Streamlit from opening a new tab
                st.markdown(
                    f'{p123_icon}{grok_icon}'
                    f'<a href="?select={urllib.parse.quote(yf_ticker)}&tv=1" '
                    f'target="_self" '
                    f'style="color:{colors["text"]};'
                    f'text-decoration:none;font-size:12px;font-weight:600;">'
                    f'{display_ticker}</a>',
                    unsafe_allow_html=True,
                )

            with c_rank:
                rank_val = row["rank"]
                rank_color = colors["red"] if 0 < rank_val < 85 else colors["text"]
                st.markdown(
                    f'<span style="color:{rank_color};font-size:12px;">'
                    f'{rank_val}</span>',
                    unsafe_allow_html=True,
                )

            with c_shares:
                st.number_input(
                    "sh", value=int(rec.get("shares", 0)),
                    step=1, min_value=0,
                    key=f"shares_{kp}",
                    label_visibility="collapsed",
                )

            with c_note:
                note_key = (sid, ticker)
                current_note = st.session_state.get("trader_notes", {}).get(
                    note_key, ""
                )
                new_note = st.text_input(
                    "n", value=current_note,
                    key=f"note_{kp}",
                    label_visibility="collapsed",
                    placeholder="...",
                )
                # Auto-save note on change
                if new_note != current_note:
                    notes = st.session_state.get("trader_notes", {})
                    st.session_state.trader_notes = set_note(
                        notes, sid, ticker, new_note
                    )
                    # If note cleared on a dummy entry, remove the dummy
                    if not new_note.strip() and row.get("is_dummy"):
                        sdata_ref = st.session_state.trader_data.get(sid)
                        if sdata_ref and rec_idx < len(sdata_ref["recs"]):
                            del sdata_ref["recs"][rec_idx]
                            st.rerun()

            prev_action = action

        st.markdown("---")

    # Commit button
    if st.button("Commit Selected", key="trader_commit_btn",
                  type="primary", use_container_width=True):
        _commit_selected()
        st.rerun()
