"""Fetch and cache fundamental data from Yahoo Finance via yfinance."""

import streamlit as st
import yfinance as yf


def _fmt_large_number(val) -> str:
    """Format large numbers: 1.5T, 391B, 12.3M, 4.2K."""
    if val is None or val == "N/A":
        return "—"
    try:
        n = float(val)
    except (TypeError, ValueError):
        return "—"
    if n == 0:
        return "0"
    neg = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1e12:
        return f"{neg}{n / 1e12:.2f}T"
    if n >= 1e9:
        return f"{neg}{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{neg}{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{neg}{n / 1e3:.1f}K"
    return f"{neg}{n:,.0f}"


def _fmt_pct(val) -> str:
    """Format a decimal ratio as percentage: 0.156 → '15.60%'."""
    if val is None or val == "N/A":
        return "—"
    try:
        return f"{float(val) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_ratio(val, decimals: int = 2) -> str:
    """Format a plain numeric ratio."""
    if val is None or val == "N/A":
        return "—"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_price(val) -> str:
    """Format a price value."""
    if val is None or val == "N/A":
        return "—"
    try:
        return f"${float(val):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _safe_get(info: dict, key: str, default=None):
    """Safely get a value from info dict, treating 'N/A' and None as missing."""
    val = info.get(key, default)
    if val is None or val == "N/A" or val == "":
        return default
    return val


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    """Fetch fundamental data for a ticker.

    Returns a dict with all fundamental fields, or empty dict on failure.
    Skips index tickers (^VIX, etc.) since they have no fundamentals.
    """
    if ticker.startswith("^") or "=" in ticker:
        return {}

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception:
        return {}

    if not info or info.get("quoteType") == "INDEX":
        return {}

    g = lambda key, default=None: _safe_get(info, key, default)  # noqa: E731

    data = {
        # ---- Identity ----
        "long_name": g("longName", ticker),
        "sector": g("sector"),
        "industry": g("industry"),
        "website": g("website"),
        "employees": g("fullTimeEmployees"),
        "current_price": g("currentPrice") or g("regularMarketPrice"),

        # ---- Overview ----
        "market_cap": g("marketCap"),
        "enterprise_value": g("enterpriseValue"),
        "beta": g("beta"),
        "52_week_high": g("fiftyTwoWeekHigh"),
        "52_week_low": g("fiftyTwoWeekLow"),
        "dividend_yield": g("dividendYield"),
        "dividend_rate": g("dividendRate"),
        "payout_ratio": g("payoutRatio"),
        "ex_dividend_date": g("exDividendDate"),

        # ---- Valuation ----
        "trailing_pe": g("trailingPE"),
        "forward_pe": g("forwardPE"),
        "peg_ratio": g("pegRatio"),
        "price_to_book": g("priceToBook"),
        "price_to_sales": g("priceToSalesTrailing12Months"),
        "ev_to_ebitda": g("enterpriseToEbitda"),
        "ev_to_revenue": g("enterpriseToRevenue"),

        # ---- Profitability ----
        "profit_margin": g("profitMargins"),
        "operating_margin": g("operatingMargins"),
        "gross_margin": g("grossMargins"),
        "return_on_equity": g("returnOnEquity"),
        "return_on_assets": g("returnOnAssets"),

        # ---- Growth & Revenue ----
        "revenue": g("totalRevenue"),
        "revenue_per_share": g("revenuePerShare"),
        "revenue_growth": g("revenueGrowth"),
        "earnings_growth": g("earningsGrowth"),

        # ---- Balance Sheet ----
        "total_cash": g("totalCash"),
        "total_debt": g("totalDebt"),
        "debt_to_equity": g("debtToEquity"),
        "current_ratio": g("currentRatio"),
        "free_cashflow": g("freeCashflow"),
        "operating_cashflow": g("operatingCashflow"),

        # ---- Analyst ----
        "target_high": g("targetHighPrice"),
        "target_low": g("targetLowPrice"),
        "target_mean": g("targetMeanPrice"),
        "target_median": g("targetMedianPrice"),
        "recommendation_key": g("recommendationKey"),
        "recommendation_mean": g("recommendationMean"),
        "num_analysts": g("numberOfAnalystOpinions"),
    }

    # Analyst estimates (DataFrames) — extract key rows
    try:
        ee = t.earnings_estimate
        if ee is not None and not ee.empty:
            rows = []
            for col in ee.columns:
                row = {"period": str(col)}
                for idx in ee.index:
                    row[str(idx).lower().replace(" ", "_")] = ee.loc[idx, col]
                rows.append(row)
            data["earnings_estimate"] = rows
    except Exception:
        pass

    try:
        re_ = t.revenue_estimate
        if re_ is not None and not re_.empty:
            rows = []
            for col in re_.columns:
                row = {"period": str(col)}
                for idx in re_.index:
                    row[str(idx).lower().replace(" ", "_")] = re_.loc[idx, col]
                rows.append(row)
            data["revenue_estimate"] = rows
    except Exception:
        pass

    return data
