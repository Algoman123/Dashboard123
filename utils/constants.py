DEFAULT_TICKER = "SPY"

BUILTIN_GROUPS = {
    "Indices": ["SPY", "QQQ", "DIA", "IWM"],
    "Sectors": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "XLC"],
}

TICKER_DISPLAY_NAMES = {
    "SPY": "S&P 500",
    "QQQ": "NASDAQ 100",
    "DIA": "Dow Jones",
    "GLD": "Gold",
    "IWM": "Russell 2000",
    "VIXY": "VIX Short",
    "^GSPC": "S&P 500",
    "^NDX": "NASDAQ 100",
    "^RUT": "Russell 2000",
    "^N100": "Euronext 100",
    "^N225": "Nikkei 225",
    "^VIX": "VIX",
    "GC=F": "Gold",
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLY": "Cons. Discr.",
    "XLP": "Cons. Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Comm. Svcs",
}

OVERVIEW_TICKERS = ["^GSPC", "^NDX", "^RUT", "^N100", "^N225", "^VIX", "GC=F"]


COLORS_DARK = {
    "bg": "#0e1117",
    "bg_secondary": "#1a1f2e",
    "bg_card": "#161b26",
    "bg_hover": "#252d3d",
    "bg_selected": "#1e3a5f",
    "text": "#e0e0e0",
    "text_header": "#ffffff",
    "text_muted": "#8b95a5",
    "green": "#10b981",
    "red": "#ef4444",
    "border": "#2d3748",
}

COLORS_LIGHT = {
    "bg": "#f9fafb",
    "bg_secondary": "#eef1f6",
    "bg_card": "#ffffff",
    "bg_hover": "#e2e7ef",
    "bg_selected": "#d0e2ff",
    "text": "#111827",
    "text_header": "#1e40af",
    "text_muted": "#6b7280",
    "green": "#059669",
    "red": "#dc2626",
    "border": "#d1d5db",
}
