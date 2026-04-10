"""Render tabbed fundamentals panel (Overview | Financials | Analyst)."""

import html as _html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from services.fundamentals_data import (
    fetch_fundamentals,
    _fmt_large_number,
    _fmt_pct,
    _fmt_ratio,
    _fmt_price,
)
from utils.constants import COLORS_DARK, COLORS_LIGHT


def _metric(label: str, value: str) -> str:
    """Single metric cell: label on top, value below."""
    return (
        f'<div class="fund-metric">'
        f'<div class="fund-metric-label">{_html.escape(label)}</div>'
        f'<div class="fund-metric-value">{_html.escape(str(value))}</div>'
        f'</div>'
    )


def _section_title(title: str) -> str:
    return f'<div class="fund-section-title">{_html.escape(title)}</div>'


def _build_overview(d: dict) -> str:
    """Build the Overview tab HTML."""
    rows = []

    # 52-Week Range
    lo = d.get("52_week_low")
    hi = d.get("52_week_high")
    range_str = f"{_fmt_price(lo)} — {_fmt_price(hi)}" if lo and hi else "—"

    # Ex-dividend date
    ex_div = d.get("ex_dividend_date")
    if ex_div:
        try:
            ex_div_str = datetime.fromtimestamp(ex_div).strftime("%b %d, %Y")
        except Exception:
            ex_div_str = str(ex_div)
    else:
        ex_div_str = "—"

    rows.append(f'<div class="fund-grid fund-grid-2">')
    rows.append(_metric("Market Cap", _fmt_large_number(d.get("market_cap"))))
    rows.append(_metric("Enterprise Value", _fmt_large_number(d.get("enterprise_value"))))
    rows.append(_metric("Beta", _fmt_ratio(d.get("beta"))))
    rows.append(_metric("52-Week Range", range_str))
    # dividendYield from yfinance is already a percentage (0.41 = 0.41%)
    div_y = d.get("dividend_yield")
    div_y_str = f"{float(div_y):.2f}%" if div_y is not None else "—"
    rows.append(_metric("Dividend Yield", div_y_str))
    rows.append(_metric("Dividend Rate", _fmt_price(d.get("dividend_rate"))))
    rows.append(_metric("Payout Ratio", _fmt_pct(d.get("payout_ratio"))))
    rows.append(_metric("Ex-Dividend Date", ex_div_str))
    rows.append('</div>')

    return "\n".join(rows)


def _build_financials(d: dict) -> str:
    """Build the Financials tab HTML — 3 column grid."""
    col1 = [  # Valuation
        _section_title("Valuation"),
        _metric("P/E (TTM)", _fmt_ratio(d.get("trailing_pe"))),
        _metric("Forward P/E", _fmt_ratio(d.get("forward_pe"))),
        _metric("PEG Ratio", _fmt_ratio(d.get("peg_ratio"))),
        _metric("Price/Book", _fmt_ratio(d.get("price_to_book"))),
        _metric("Price/Sales", _fmt_ratio(d.get("price_to_sales"))),
        _metric("EV/EBITDA", _fmt_ratio(d.get("ev_to_ebitda"))),
    ]

    col2 = [  # Profitability
        _section_title("Profitability"),
        _metric("Profit Margin", _fmt_pct(d.get("profit_margin"))),
        _metric("Operating Margin", _fmt_pct(d.get("operating_margin"))),
        _metric("ROE", _fmt_pct(d.get("return_on_equity"))),
        _metric("ROA", _fmt_pct(d.get("return_on_assets"))),
        _metric("Revenue Growth", _fmt_pct(d.get("revenue_growth"))),
        _metric("Earnings Growth", _fmt_pct(d.get("earnings_growth"))),
    ]

    col3 = [  # Balance Sheet
        _section_title("Balance Sheet"),
        _metric("Revenue", _fmt_large_number(d.get("revenue"))),
        _metric("Total Cash", _fmt_large_number(d.get("total_cash"))),
        _metric("Total Debt", _fmt_large_number(d.get("total_debt"))),
        _metric("Debt/Equity", _fmt_ratio(d.get("debt_to_equity"))),
        _metric("Current Ratio", _fmt_ratio(d.get("current_ratio"))),
        _metric("Free Cash Flow", _fmt_large_number(d.get("free_cashflow"))),
    ]

    return (
        '<div class="fund-grid fund-grid-3">'
        f'<div class="fund-col">{"".join(col1)}</div>'
        f'<div class="fund-col">{"".join(col2)}</div>'
        f'<div class="fund-col">{"".join(col3)}</div>'
        '</div>'
    )


def _rec_badge(key: str, mean_score) -> str:
    """Render a recommendation badge with colour coding."""
    if not key:
        return ""
    label = key.replace("_", " ").title()
    # Colour: green for buy, yellow for hold, red for sell
    colors = {
        "strong_buy": "#10b981",
        "buy": "#10b981",
        "hold": "#eab308",
        "underperform": "#f97316",
        "sell": "#ef4444",
        "strong_sell": "#ef4444",
    }
    color = colors.get(key, "#8b95a5")
    mean_str = f" ({_fmt_ratio(mean_score, 1)})" if mean_score else ""
    return (
        f'<span class="fund-rec-badge" style="background:{color}22;color:{color};'
        f'border:1px solid {color}44">{_html.escape(label)}{mean_str}</span>'
    )


def _build_target_bar(d: dict) -> str:
    """Build the price target horizontal bar visualisation."""
    lo = d.get("target_low")
    hi = d.get("target_high")
    mean = d.get("target_mean")
    current = d.get("current_price")

    if not lo or not hi or not mean:
        return ""

    try:
        lo, hi, mean = float(lo), float(hi), float(mean)
    except (TypeError, ValueError):
        return ""

    span = hi - lo
    if span <= 0:
        return ""

    mean_pct = max(0, min(100, (mean - lo) / span * 100))

    # Current price marker
    current_marker = ""
    if current:
        try:
            cur = float(current)
            cur_pct = max(0, min(100, (cur - lo) / span * 100))
            current_marker = (
                f'<div class="fund-target-current" style="left:{cur_pct:.1f}%">'
                f'<div class="fund-target-current-dot"></div>'
                f'<div class="fund-target-current-label">{_fmt_price(cur)}</div>'
                f'</div>'
            )
        except (TypeError, ValueError):
            pass

    return (
        f'<div class="fund-target-wrap">'
        f'<div class="fund-target-labels">'
        f'<span>Low {_fmt_price(lo)}</span>'
        f'<span>Mean {_fmt_price(mean)}</span>'
        f'<span>High {_fmt_price(hi)}</span>'
        f'</div>'
        f'<div class="fund-target-bar">'
        f'<div class="fund-target-fill" style="width:{mean_pct:.1f}%"></div>'
        f'{current_marker}'
        f'</div>'
        f'</div>'
    )


def _build_estimate_table(estimates: list, fmt_fn, label: str) -> str:
    """Build a simple HTML table for earnings/revenue estimates."""
    if not estimates:
        return ""

    header_cells = "".join(
        f'<th>{_html.escape(str(e.get("period", "")))}</th>'
        for e in estimates[:4]
    )

    # Try to extract relevant rows
    row_keys = []
    if estimates:
        sample = estimates[0]
        for k in sample:
            if k != "period":
                row_keys.append(k)

    body_rows = []
    for rk in row_keys[:6]:
        display_name = rk.replace("_", " ").title()
        cells = ""
        for e in estimates[:4]:
            val = e.get(rk)
            cells += f'<td>{fmt_fn(val)}</td>'
        body_rows.append(f'<tr><td class="fund-est-label">{_html.escape(display_name)}</td>{cells}</tr>')

    if not body_rows:
        return ""

    return (
        f'<div class="fund-section-title">{_html.escape(label)}</div>'
        f'<table class="fund-est-table">'
        f'<thead><tr><th></th>{header_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table>'
    )


def _build_analyst(d: dict) -> str:
    """Build the Analyst tab HTML."""
    parts = []

    # Recommendation badge
    rec_key = d.get("recommendation_key")
    rec_mean = d.get("recommendation_mean")
    num = d.get("num_analysts")
    if rec_key or num:
        badge = _rec_badge(rec_key, rec_mean)
        analysts_str = f'<span class="fund-analysts-count">{int(num)} analysts</span>' if num else ""
        parts.append(f'<div class="fund-rec-row">{badge}{analysts_str}</div>')

    # Price target bar
    bar = _build_target_bar(d)
    if bar:
        parts.append(bar)

    # Earnings estimates
    ee = d.get("earnings_estimate")
    if ee:
        parts.append(_build_estimate_table(ee, lambda v: _fmt_ratio(v), "Earnings Estimate (EPS)"))

    # Revenue estimates
    re_ = d.get("revenue_estimate")
    if re_:
        parts.append(_build_estimate_table(re_, lambda v: _fmt_large_number(v), "Revenue Estimate"))

    if not parts:
        parts.append('<div class="fund-metric-label" style="padding:12px 0">No analyst data available</div>')

    return "\n".join(parts)


def _fund_css(c: dict) -> str:
    """Generate self-contained CSS for the fundamentals iframe."""
    return f"""
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;700&display=swap');
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Nunito Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        background: transparent;
        color: {c['text']};
    }}
    .fund-header {{
        font-size: 12px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.5px; padding: 2px 8px; margin-bottom: 2px;
        display: flex; align-items: center; gap: 6px; color: {c['text_muted']};
    }}
    .fund-header-link, .fund-header-link:visited {{ font-size: 14px; color: {c['text_muted']}88; text-decoration: none; }}
    .fund-header-link:hover {{ color: {c['green']}; }}
    .fund-profile {{
        font-size: 12px; color: {c['text_muted']}bb; padding: 0 8px 8px; line-height: 1.4;
    }}
    .fund-profile-link, .fund-profile-link:visited {{ color: {c['text_muted']}; text-decoration: none; }}
    .fund-profile-link:hover {{ color: {c['green']}; text-decoration: underline; }}
    .fund-tab-labels {{
        display: flex; gap: 0; padding: 0 8px; border-bottom: 1px solid {c['border']}44; margin-bottom: 10px;
    }}
    .fund-tab-label {{
        font-size: 12px; font-weight: 600; padding: 6px 16px; cursor: pointer;
        color: {c['text_muted']}; border-bottom: 2px solid transparent;
        transition: color 0.15s, border-color 0.15s; user-select: none;
    }}
    .fund-tab-label:hover {{ color: {c['text']}; }}
    .fund-tab-active {{ color: {c['green']} !important; border-bottom-color: {c['green']} !important; }}
    .fund-panel {{ padding: 4px 8px 12px; }}
    .fund-grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; }}
    .fund-grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px 16px; }}
    .fund-col {{ display: flex; flex-direction: column; gap: 6px; }}
    .fund-metric {{
        display: flex; justify-content: space-between; align-items: baseline;
        padding: 3px 0; border-bottom: 1px solid {c['border']}22;
    }}
    .fund-metric-label {{ font-size: 11px; color: {c['text_muted']}99; }}
    .fund-metric-value {{ font-size: 13px; font-weight: 600; color: {c['text']}; }}
    .fund-section-title {{
        font-size: 11px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.4px; color: {c['text_muted']}; padding: 6px 0 4px; margin-bottom: 2px;
    }}
    .fund-rec-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
    .fund-rec-badge {{ font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 4px; display: inline-block; }}
    .fund-analysts-count {{ font-size: 12px; color: {c['text_muted']}99; }}
    .fund-target-wrap {{ margin-bottom: 16px; }}
    .fund-target-labels {{
        display: flex; justify-content: space-between; font-size: 11px;
        color: {c['text_muted']}99; margin-bottom: 4px; padding: 0 2px;
    }}
    .fund-target-bar {{
        position: relative; height: 8px; border-radius: 4px; background: {c['border']}44; overflow: visible;
    }}
    .fund-target-fill {{ height: 100%; border-radius: 4px; background: {c['green']}88; }}
    .fund-target-current {{ position: absolute; top: -3px; transform: translateX(-50%); }}
    .fund-target-current-dot {{
        width: 14px; height: 14px; border-radius: 50%; background: {c['text']}; border: 2px solid {c['bg']};
    }}
    .fund-target-current-label {{
        font-size: 10px; font-weight: 600; color: {c['text']}; text-align: center; margin-top: 2px; white-space: nowrap;
    }}
    .fund-est-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 12px; }}
    .fund-est-table th {{
        font-weight: 600; color: {c['text_muted']}; text-align: right; padding: 4px 8px;
        border-bottom: 1px solid {c['border']}33; font-size: 11px;
    }}
    .fund-est-table td {{
        text-align: right; padding: 4px 8px; color: {c['text']}; border-bottom: 1px solid {c['border']}22;
    }}
    .fund-est-label {{ text-align: left !important; color: {c['text_muted']}99; font-size: 11px; }}
    """


def render_fundamentals(ticker: str, colors: dict):
    """Render the tabbed fundamentals panel below the news section."""
    # Skip index tickers and futures
    if ticker.startswith("^") or "=" in ticker:
        return

    data = fetch_fundamentals(ticker)
    if not data:
        return

    theme = st.session_state.get("theme", "dark")
    c = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # Yahoo Finance link
    yf_url = f"https://finance.yahoo.com/quote/{ticker}/key-statistics/"

    # Company profile line
    profile_parts = []
    if data.get("sector"):
        profile_parts.append(data["sector"])
    if data.get("industry"):
        profile_parts.append(data["industry"])
    if data.get("employees"):
        try:
            profile_parts.append(f"{int(data['employees']):,} employees")
        except (TypeError, ValueError):
            pass
    if data.get("website"):
        w = _html.escape(data["website"])
        domain = w.replace("https://", "").replace("http://", "").rstrip("/")
        profile_parts.append(f'<a href="{w}" target="_blank" class="fund-profile-link">{domain}</a>')

    profile_html = " · ".join(profile_parts) if profile_parts else ""

    # Build tab content
    overview_html = _build_overview(data)
    financials_html = _build_financials(data)
    analyst_html = _build_analyst(data)

    company_name = _html.escape(data.get("long_name", ticker))

    # Rendered inside components.html() iframe so scripts execute properly
    # and tab switching works without Streamlit reruns.
    full_html = f"""<!DOCTYPE html>
<html>
<head><style>{_fund_css(c)}</style></head>
<body>
    <div class="fund-header">
        <span>Fundamentals &mdash; {company_name}</span>
        <a href="{yf_url}" target="_blank" class="fund-header-link"
           title="View on Yahoo Finance">&#8599;</a>
    </div>
    <div class="fund-profile">{profile_html}</div>
    <div class="fund-tab-labels">
        <span class="fund-tab-label fund-tab-active" data-fund-tab="0">Overview</span>
        <span class="fund-tab-label" data-fund-tab="1">Financials</span>
        <span class="fund-tab-label" data-fund-tab="2">Analyst</span>
    </div>
    <div class="fund-panels">
        <div class="fund-panel" style="display:block">{overview_html}</div>
        <div class="fund-panel" style="display:none">{financials_html}</div>
        <div class="fund-panel" style="display:none">{analyst_html}</div>
    </div>
    <script>
    (function() {{
        var tabs = document.querySelectorAll('[data-fund-tab]');
        var panels = document.querySelectorAll('.fund-panel');

        function resize() {{
            // Tell Streamlit iframe to match content height
            var h = document.body.scrollHeight + 4;
            window.frameElement && (window.frameElement.style.height = h + 'px');
        }}

        tabs.forEach(function(tab) {{
            tab.addEventListener('click', function() {{
                var idx = parseInt(this.getAttribute('data-fund-tab'));
                tabs.forEach(function(t) {{ t.classList.remove('fund-tab-active'); }});
                this.classList.add('fund-tab-active');
                panels.forEach(function(p, i) {{ p.style.display = (i === idx) ? 'block' : 'none'; }});
                resize();
            }});
        }});

        // Initial resize after render
        resize();
    }})();
    </script>
</body>
</html>"""

    components.html(full_html, height=520, scrolling=False)
