"""Indicator registry and formatting for sidebar columns."""

import math

# ---- Indicator definitions ----
# key  → label (for settings UI), header (short, for sidebar column header)

INDICATORS = {
    # Return-based (already computed in market_data)
    "Daily": {"label": "Daily", "header": "Day", "type": "pct"},
    "5D":    {"label": "5 Day", "header": "5D",  "type": "pct"},
    "1M":    {"label": "1 Month", "header": "1M", "type": "pct"},
    "3M":    {"label": "3 Month", "header": "3M", "type": "pct"},
    "1Y":    {"label": "1 Year", "header": "1Y",  "type": "pct"},
    # Technical indicators (computed in market_data)
    "RSI":    {"label": "RSI (14)", "header": "RSI",  "type": "rsi"},
    "SMA20":  {"label": "vs SMA 20", "header": "MA20", "type": "pct"},
    "SMA50":  {"label": "vs SMA 50", "header": "MA50", "type": "pct"},
    "SMA200": {"label": "vs SMA 200", "header": "M200", "type": "pct"},
    "RVOL":   {"label": "Rel. Volume", "header": "RVol", "type": "rvol"},
}

# Ordered mapping for selectbox UIs: human label → key
INDICATOR_OPTIONS = {meta["label"]: key for key, meta in INDICATORS.items()}


def format_indicator(key: str, value, colors: dict) -> tuple[str, str]:
    """Format an indicator value for sidebar display.

    Returns (display_text, css_color).
    """
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "N/A", colors["text_muted"]

    meta = INDICATORS.get(key, {})
    itype = meta.get("type", "pct")

    if itype == "pct":
        sign = "+" if value >= 0 else ""
        text = f"{sign}{value:.1f}%"
        if value > 0:
            color = colors["green"]
        elif value < 0:
            color = colors["red"]
        else:
            color = colors["text_muted"]
        return text, color

    if itype == "rsi":
        text = f"{value:.0f}"
        if value >= 70:
            color = colors["red"]       # overbought
        elif value <= 30:
            color = colors["green"]     # oversold
        else:
            color = colors["text_muted"]
        return text, color

    if itype == "rvol":
        text = f"{value:.1f}x"
        color = colors["green"] if value >= 1.5 else colors["text_muted"]
        return text, color

    # Fallback
    return str(round(value, 1)), colors["text_muted"]
