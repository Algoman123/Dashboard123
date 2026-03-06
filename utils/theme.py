from utils.constants import COLORS_DARK, COLORS_LIGHT


def get_theme_css(theme: str) -> str:
    c = COLORS_DARK if theme == "dark" else COLORS_LIGHT
    return f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;700&display=swap');
    /* ---- Global overrides for light/dark ---- */
    .stApp {{
        background-color: {c['bg']} !important;
        color: {c['text']} !important;
    }}
    .stApp [data-testid="stHeader"] {{
        background-color: {c['bg']} !important;
    }}

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {{
        background-color: {c['bg_secondary']} !important;
    }}
    [data-testid="stSidebar"] > div {{
        background-color: {c['bg_secondary']} !important;
        padding-top: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
        padding-top: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: hidden !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
        padding-top: 0.25rem !important;
    }}
    [data-testid="stSidebar"] > div > div > div > [data-testid="stVerticalBlock"] {{
        gap: 0.4rem !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        color: {c['text']} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
        color: {c['text_muted']} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
        color: {c['text_header']} !important;
    }}
    [data-testid="stSidebar"] hr {{
        border-color: {c['border']} !important;
    }}

    /* ---- Sidebar buttons (header icons) ---- */
    [data-testid="stSidebar"] button {{
        color: {c['text']} !important;
        background-color: {c['bg_card']} !important;
        border: 1px solid {c['border']} !important;
    }}
    [data-testid="stSidebar"] button:hover {{
        background-color: {c['bg_hover']} !important;
    }}

    /* ---- Expander headers ---- */
    [data-testid="stSidebar"] [data-testid="stExpander"] details {{
        border: 1px solid {c['border']} !important;
        border-radius: 8px;
        background-color: {c['bg_card']} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        color: {c['text_header']} !important;
        font-weight: 700;
        font-size: 14px;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        color: {c['green']} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
        fill: {c['text_muted']} !important;
    }}

    /* ---- Ticker buttons inside expanders ---- */
    [data-testid="stSidebar"] [data-testid="stExpander"] button {{
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid {c['border']}33 !important;
        border-radius: 0 !important;
        color: {c['text_muted']} !important;
        padding: 2px 4px !important;
        margin: 0 !important;
        font-family: 'Consolas', 'SF Mono', 'Courier New', monospace !important;
        font-size: 12px !important;
        text-align: left !important;
        white-space: pre !important;
        transition: background 0.12s;
        min-height: 0 !important;
        line-height: 1.3 !important;
        justify-content: flex-start !important;
    }}
    /* Force left-align sidebar button inner content (Streamlit nests div>span>div>p inside button) */
    [data-testid="stSidebar"] [data-testid="stExpander"] button div,
    [data-testid="stSidebar"] [data-testid="stExpander"] button span {{
        justify-content: flex-start !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] button p {{
        text-align: left !important;
        width: 100% !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid*="stBaseButton"] {{
        justify-content: flex-start !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] button:hover {{
        background: {c['bg_hover']} !important;
    }}
    /* ---- Reduce gap between ticker buttons ---- */
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
        gap: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stElementContainer"] {{
        margin: 0 !important;
        padding: 0 !important;
        overflow: visible !important;
    }}
    /* ---- Column header spacing ---- */
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stElementContainer"]:has(.ticker-col-header) {{
        padding-top: 6px !important;
    }}
    /* ---- Column header inside expanders ---- */
    .ticker-col-header {{
        display: flex;
        font-family: 'Consolas', 'SF Mono', 'Courier New', monospace;
        font-size: 10px;
        color: {c['text_muted']}88;
        padding: 10px 4px 2px 4px;
        margin-bottom: 8px;
    }}
    /* ---- Percentage cells next to ticker buttons ---- */
    .pct-cell {{
        font-family: 'Consolas', 'SF Mono', 'Courier New', monospace;
        font-size: 11px;
        font-weight: 600;
        text-align: right;
        padding: 2px 0;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
    }}
    /* ---- Tighten column gaps inside expanders ---- */
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stHorizontalBlock"] {{
        gap: 0 !important;
        align-items: baseline;
    }}

    /* ---- Metric cards ---- */
    .metric-card {{
        background: {c['bg_card']} !important;
        border-radius: 10px;
        padding: 14px 16px;
        text-align: center;
        border: 1px solid {c['border']};
        transition: transform 0.15s;
    }}
    .metric-card:hover {{
        transform: translateY(-2px);
    }}
    .metric-card .label {{
        font-size: 13px;
        font-weight: 600;
        color: {c['text_muted']} !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}
    .metric-card .price {{
        font-size: 20px;
        font-weight: 700;
        color: {c['text']} !important;
        margin-bottom: 2px;
    }}
    .metric-card .change {{
        font-size: 14px;
        font-weight: 600;
    }}
    .positive {{ color: {c['green']} !important; }}
    .negative {{ color: {c['red']} !important; }}

    /* ---- Detail panel ---- */
    .detail-panel {{
        background: {c['bg_card']} !important;
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 16px 20px;
        margin-top: 8px;
    }}
    .detail-panel .ticker-name {{
        font-size: 22px;
        font-weight: 700;
        color: {c['text']} !important;
    }}

    /* ---- Membership badges (detail panel) ---- */
    .membership-badge {{
        display: inline-flex;
        align-items: center;
        font-size: 13px;
        padding: 3px 10px;
        border-radius: 4px;
        background: {c['bg_card']};
        color: {c['text_muted']};
        white-space: nowrap;
    }}

    /* ---- Main area text colors ---- */
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] span {{
        color: {c['text']};
    }}

    /* ---- Reduce top padding in main area ---- */
    .block-container {{
        padding-top: 0.5rem !important;
    }}
    .stApp [data-testid="stHeader"] {{
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }}

    /* ---- Movers (gainers/losers) section ---- */
    .movers-header {{
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 2px 8px;
        margin-bottom: 6px;
    }}
    /* Reduce gaps in movers container — use direct-child :has(>) to avoid leaking to entire page */
    /* Target the inner columns (col_gain/col_lose) that directly contain .movers-header */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .movers-header) {{
        gap: 0 !important;
    }}
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .movers-header) > [data-testid="stElementContainer"] {{
        margin: 0 !important;
        padding: 0 !important;
    }}
    /* Target the movers wrapper that directly contains .movers-section marker */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .movers-section) {{
        gap: 0 !important;
    }}
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .movers-section) > [data-testid="stElementContainer"] {{
        margin: 0 !important;
        padding: 0 !important;
    }}
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .movers-section) > [data-testid="stHorizontalBlock"] {{
        gap: 0 !important;
    }}
    /* Tighten forum section to match movers */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .forum-header) {{
        gap: 0 !important;
    }}
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .forum-header) > [data-testid="stElementContainer"] {{
        margin: 0 !important;
        padding: 0 !important;
    }}
    /* Mover rows (pure HTML flex layout) */
    .mover-row {{
        display: flex;
        align-items: center;
        padding: 3px 8px;
        border-bottom: 1px solid {c['border']}33;
        font-family: 'Consolas', 'SF Mono', 'Courier New', monospace;
        font-size: 12px;
        line-height: 1.6;
    }}
    .mover-row:hover {{
        background: {c['bg_hover']};
    }}
    .mover-row .mover-ticker, .mover-row .mover-ticker:visited, .mover-row .mover-ticker:hover, .mover-row .mover-ticker:active {{
        flex: 3;
        color: {c['text_muted']};
        text-decoration: none !important;
        white-space: nowrap;
    }}
    .mover-row .mover-ticker:hover {{
        color: {c['text']} !important;
    }}
    .mover-row .mover-price {{
        flex: 2;
        text-align: right;
        color: {c['text_muted']};
    }}
    .mover-row .mover-change {{
        flex: 1.5;
        text-align: right;
        font-weight: 700;
    }}
    /* P123 link icon (sidebar + movers) */
    .p123-link, .p123-link:visited, .p123-link:hover, .p123-link:active {{
        color: {c['text_muted']}88;
        text-decoration: none !important;
        width: 14px;
        flex-shrink: 0;
        text-align: center;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }}
    .p123-link:hover {{
        color: {c['green']} !important;
    }}
    .p123-link svg {{
        display: block;
    }}
    /* Grok AI link icon */
    .grok-link, .grok-link:visited, .grok-link:hover, .grok-link:active {{
        color: {c['text_muted']}88;
        text-decoration: none !important;
        width: 14px;
        flex-shrink: 0;
        text-align: center;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-right: 2px;
    }}
    .grok-link:hover {{
        color: {c['green']} !important;
    }}
    .grok-link svg {{
        display: block;
    }}

    /* ---- Forum posts section ---- */
    .forum-header {{
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 2px 8px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
        color: {c['text_muted']};
    }}
    .forum-header-link, .forum-header-link:visited, .forum-header-link:hover, .forum-header-link:active {{
        font-size: 14px;
        color: {c['text_muted']}88;
        text-decoration: none !important;
    }}
    .forum-header-link:hover {{
        color: {c['green']} !important;
    }}
    .forum-row {{
        display: flex;
        align-items: center;
        padding: 5px 8px;
        border-bottom: 1px solid {c['border']}33;
        font-size: 13px;
        line-height: 1.5;
        gap: 8px;
    }}
    .forum-row:hover {{
        background: {c['bg_hover']};
    }}
    .forum-category {{
        font-size: 10px;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 3px;
        white-space: nowrap;
        flex-shrink: 0;
        min-width: 60px;
        text-align: center;
    }}
    .forum-title, .forum-title:visited, .forum-title:hover, .forum-title:active {{
        flex: 1;
        color: {c['text_muted']};
        text-decoration: none !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }}
    .forum-title:hover {{
        color: {c['text']} !important;
    }}
    .forum-meta {{
        font-size: 11px;
        color: {c['text_muted']}88;
        flex-shrink: 0;
        min-width: 30px;
        text-align: right;
    }}
    .forum-time {{
        min-width: 28px;
    }}

    /* ---- Trader Panel ---- */
    /* Scope: everything after the trader-panel-marker in the same column */

    /* Reduce vertical gap between trader rows */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stVerticalBlock"] {{
        gap: 0.25rem !important;
    }}

    /* Align all items in trader horizontal rows to center vertically */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stHorizontalBlock"] {{
        align-items: center !important;
        gap: 0.25rem !important;
    }}

    /* Compact number inputs inside trader panel */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stNumberInput"] input {{
        padding: 2px 6px !important;
        font-size: 12px !important;
        height: 30px !important;
    }}
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stNumberInput"] button {{
        display: none !important;
    }}
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stNumberInput"] {{
        margin-bottom: 0 !important;
    }}

    /* Compact text inputs inside trader panel */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stTextInput"] input {{
        padding: 2px 6px !important;
        font-size: 12px !important;
        height: 30px !important;
    }}
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stTextInput"] {{
        margin-bottom: 0 !important;
    }}

    /* Compact checkboxes inside trader panel */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stCheckbox"] {{
        margin-bottom: 0 !important;
    }}
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stCheckbox"] label {{
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        min-height: 0 !important;
        align-items: center !important;
    }}

    /* Remove excess padding on markdown inside trader rows */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stMarkdownContainer"] {{
        padding: 0 !important;
    }}
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stMarkdownContainer"] p {{
        margin-bottom: 0 !important;
        line-height: 30px !important;
    }}

    /* Remove element container margin in trader panel rows */
    [data-testid="stColumn"]:has(.trader-panel-marker) [data-testid="stHorizontalBlock"] [data-testid="stColumn"] [data-testid="stElementContainer"] {{
        margin: 0 !important;
        padding: 0 !important;
    }}

    /* Add a bit of left padding to the whole trader panel */
    [data-testid="stColumn"]:has(.trader-panel-marker) {{
        padding-left: 12px !important;
    }}

    /* ---- News section ---- */
    .news-header {{
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 2px 8px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
        color: {c['text_muted']};
    }}
    .news-header-link, .news-header-link:visited, .news-header-link:hover, .news-header-link:active {{
        font-size: 14px;
        color: {c['text_muted']}88;
        text-decoration: none !important;
    }}
    .news-header-link:hover {{
        color: {c['green']} !important;
    }}
    .news-item, .news-item:visited, .news-item:active {{
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 12px 8px;
        border-bottom: 1px solid {c['border']}33;
        text-decoration: none !important;
        color: inherit;
        transition: background 0.12s;
    }}
    .news-item:hover {{
        background: {c['bg_hover']};
    }}
    .news-thumb {{
        width: 120px;
        height: 80px;
        border-radius: 6px;
        object-fit: cover;
        flex-shrink: 0;
        background: {c['bg_card']};
    }}
    .news-thumb-placeholder {{
        border: 1px solid {c['border']}44;
    }}
    .news-content {{
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }}
    .news-meta {{
        font-size: 11px;
        color: {c['text_muted']}99;
        display: flex;
        align-items: center;
        gap: 4px;
    }}
    .news-source {{
        font-weight: 600;
        color: {c['text_muted']};
    }}
    .news-time {{
        color: {c['text_muted']}88;
    }}
    .news-title {{
        font-size: 14px;
        font-weight: 600;
        color: {c['text']};
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}
    .news-summary {{
        font-size: 12px;
        color: {c['text_muted']}bb;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    /* ---- News Feed Panel (right column) ---- */
    /* Scope via .news-feed-marker — same pattern as trader panel */
    [data-testid="stColumn"]:has(.news-feed-marker) [data-testid="stVerticalBlock"] {{
        gap: 0.25rem !important;
    }}
    [data-testid="stColumn"]:has(.news-feed-marker) {{
        padding-left: 12px !important;
    }}
    [data-testid="stColumn"]:has(.news-feed-marker) [data-testid="stMarkdownContainer"] {{
        padding: 0 !important;
    }}
    /* News feed item styling */
    .nf-item, .nf-item:visited, .nf-item:active {{
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 10px 4px;
        border-bottom: 1px solid {c['border']}33;
        text-decoration: none !important;
        color: inherit;
        transition: background 0.12s;
    }}
    .nf-item:hover {{
        background: {c['bg_hover']};
    }}
    .nf-thumb {{
        width: 80px;
        height: 56px;
        border-radius: 4px;
        object-fit: cover;
        flex-shrink: 0;
        background: {c['bg_card']};
        display: block;
    }}
    .nf-thumb-placeholder {{
        border: 1px solid {c['border']}44;
    }}
    .nf-list {{
        display: flex;
        flex-direction: column;
    }}
    .nf-content {{
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }}
    .nf-meta {{
        font-size: 10px;
        color: {c['text_muted']}99;
        display: flex;
        align-items: center;
        gap: 4px;
        flex-wrap: wrap;
    }}
    .nf-ticker, .nf-ticker:visited, .nf-ticker:active {{
        font-size: 10px;
        font-weight: 700;
        padding: 0px 5px;
        border-radius: 3px;
        background: {c['bg_card']};
        border: 1px solid {c['border']}44;
        color: {c['text']} !important;
        text-decoration: none !important;
        white-space: nowrap;
    }}
    .nf-ticker:hover {{
        background: {c['bg_hover']} !important;
        color: {c['green']} !important;
    }}
    .nf-source {{
        font-weight: 600;
        color: {c['text_muted']};
    }}
    .nf-time {{
        color: {c['text_muted']}88;
    }}
    .nf-title {{
        font-size: 13px;
        font-weight: 600;
        color: {c['text']};
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}
    .nf-summary {{
        font-size: 11px;
        color: {c['text_muted']}bb;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 1;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    /* ---- Hide Streamlit defaults ---- */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    [data-testid="stToolbar"] {{display: none !important;}}
    </style>"""
