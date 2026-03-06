import os
import warnings
import streamlit as st
import p123api
import yfinance as yf
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# P123 exchange suffix -> yfinance suffix mapping
_EXCHANGE_MAP = {
    "USA": "",
    "SWE": ".ST",
    "NOR": ".OL",
    "FIN": ".HE",
    "DEU": ".DE",
    "GBR": ".L",
    "FRA": ".PA",
    "AUS": ".AX",
    "JPN": ".T",
    "HKG": ".HK",
    "SGP": ".SI",
    "NLD": ".AS",
    "BEL": ".BR",
    "ESP": ".MC",
    "ITA": ".MI",
    "CHE": ".SW",
    "AUT": ".VI",
    "IRL": ".IR",
    "PRT": ".LS",
    "DNK": ".CO",
    "GRC": ".AT",
    "LUX": ".LU",
    "NZL": ".NZ",
    "ISR": ".TA",
}


@st.cache_data(ttl=86400, show_spinner=False)
def _resolve_canadian_suffix(symbol: str) -> str:
    """Determine if a Canadian stock trades on TSX (.TO) or TSXV (.V).

    P123 uses 'CAN' for both exchanges, so we check Yahoo Finance
    to find the correct suffix.  Result is cached for 24 hours.
    """
    # Suppress yfinance "possibly delisted" warnings during probing
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Try TSX first (larger exchange, more common)
        try:
            hist = yf.Ticker(f"{symbol}.TO").history(period="1mo")
            if len(hist) > 0:
                return ".TO"
        except Exception:
            pass
        # Try TSX Venture
        try:
            hist = yf.Ticker(f"{symbol}.V").history(period="1mo")
            if len(hist) > 0:
                return ".V"
        except Exception:
            pass
    # Default to TSX if neither resolves
    return ".TO"


def _p123_to_yfinance(ticker: str) -> str:
    """Convert P123 ticker format (e.g. 'EDRY:USA') to yfinance format (e.g. 'EDRY').

    P123 uses dots for share-class separators (e.g. BERNER.B:SWE) while
    Yahoo Finance uses dashes (BERNER-B.ST), so dots in the symbol part
    are replaced with dashes for non-US tickers.
    """
    if ":" not in ticker:
        return ticker
    symbol, exchange = ticker.rsplit(":", 1)
    # Canadian stocks need special handling: P123 uses 'CAN' for both TSX and TSXV
    if exchange == "CAN":
        yf_symbol = symbol.replace(".", "-")
        suffix = _resolve_canadian_suffix(yf_symbol)
        return yf_symbol + suffix
    suffix = _EXCHANGE_MAP.get(exchange, "")
    # Yahoo uses dashes for share-class dots (e.g. BERNER.B -> BERNER-B)
    if suffix:
        symbol = symbol.replace(".", "-")
    return symbol + suffix


# Reverse map: yfinance suffix -> P123 country code
_YF_SUFFIX_TO_P123 = {v: k for k, v in _EXCHANGE_MAP.items() if v}
# Both TSX (.TO) and TSXV (.V) map back to CAN for P123 links
_YF_SUFFIX_TO_P123[".TO"] = "CAN"
_YF_SUFFIX_TO_P123[".V"] = "CAN"


def p123_stock_url(yf_ticker: str) -> str | None:
    """Build a Portfolio123 stock page URL from a yfinance ticker.

    Returns None for index tickers (^VIX etc.) that have no P123 page.
    """
    if yf_ticker.startswith("^"):
        return None

    for suffix, country in _YF_SUFFIX_TO_P123.items():
        if yf_ticker.endswith(suffix):
            symbol = yf_ticker[: -len(suffix)].replace("-", ".")
            return f"https://www.portfolio123.com/app/stock?tab=timeline&t={symbol}:{country}"

    # US ticker (no suffix) — always include :USA for reliable P123 links
    return f"https://www.portfolio123.com/app/stock?tab=timeline&t={yf_ticker}:USA"


def get_p123_client():
    """Create P123 client from .env credentials. Returns None if not configured."""
    api_id = os.getenv("P123_API_ID")
    api_key = os.getenv("P123_API_KEY")
    if not api_id or not api_key:
        return None
    try:
        return p123api.Client(api_id=api_id, api_key=api_key)
    except Exception:
        return None


def is_p123_configured() -> bool:
    """Check if P123 API credentials are set in .env."""
    api_id = os.getenv("P123_API_ID")
    api_key = os.getenv("P123_API_KEY")
    return bool(api_id and api_key and api_id != "your_api_id_here")


def fetch_strategy_holdings(strategy_id: int) -> tuple[list[str], int | None]:
    """Fetch ticker list for a P123 strategy.

    NOT cached — holdings are persisted to disk and only refreshed
    on manual button press to conserve API credits.
    """
    client = get_p123_client()
    if client is None:
        return [], None
    try:
        raw = client.strategy_holdings(strategy_id)  # raw dict keeps quotaRemaining
        quota = raw.get("quotaRemaining") if isinstance(raw, dict) else None
        # Build DataFrame from the holdings list
        import pandas as pd
        df = pd.DataFrame(raw.get("holdings", []) if isinstance(raw, dict) else raw)
        # Find the ticker column (case-insensitive)
        ticker_col = None
        for col in df.columns:
            if col.lower() in ("ticker", "symbol", "tickers"):
                ticker_col = col
                break
        if ticker_col:
            raw_tickers = df[ticker_col].tolist()
        elif len(df.columns) > 0:
            raw_tickers = df.iloc[:, 0].tolist()
        else:
            return [], quota
        # Convert P123 format (TICKER:EXCHANGE) to yfinance format
        return [_p123_to_yfinance(t) for t in raw_tickers], quota
    except Exception:
        return [], None


def fetch_screen_holdings(screen_id: int, max_holdings: int = 50) -> tuple[list[str], int | None]:
    """Fetch ticker list for a P123 screen.

    NOT cached — holdings are persisted to disk and only refreshed
    on manual button press to conserve API credits.
    """
    client = get_p123_client()
    if client is None:
        return [], None
    try:
        params = {"screen": {"id": screen_id, "maxNumHoldings": max_holdings}}
        raw = client.screen_run(params)  # raw dict keeps quotaRemaining
        quota = raw.get("quotaRemaining") if isinstance(raw, dict) else None
        # Build DataFrame from rows/columns
        import pandas as pd
        df = pd.DataFrame(
            data=raw.get("rows", []),
            columns=raw.get("columns", []),
        ) if isinstance(raw, dict) else pd.DataFrame(raw)
        # Find the ticker column (case-insensitive)
        ticker_col = None
        for col in df.columns:
            if col.lower() in ("ticker", "symbol", "tickers"):
                ticker_col = col
                break
        if ticker_col:
            raw_tickers = df[ticker_col].tolist()
        elif len(df.columns) > 0:
            raw_tickers = df.iloc[:, 0].tolist()
        else:
            return [], quota
        # Convert P123 format (TICKER:EXCHANGE) to yfinance format
        return [_p123_to_yfinance(t) for t in raw_tickers], quota
    except Exception:
        return [], None


def fetch_ranking_holdings(ranking_id: int, universe: str) -> tuple[list[str], dict | None, int | None]:
    """Fetch ALL ranked tickers + composite node scores from a P123 ranking system.

    Returns (yf_tickers, nodes_data, quota).
    - yf_tickers: full universe-ranked list (callers slice for sidebar display)
    - nodes_data: {"names": [...], "weights": [...], "scores": {ticker: [score, ...]}}
      or None if no composite nodes exist
    - quota: remaining API credits

    Uses nodeDetails='composite' to get per-node rank breakdown at no
    extra API credit cost (~2 credits per call regardless of size).

    NOT cached — data is persisted to disk and only refreshed on manual
    button press to conserve API credits.
    """
    client = get_p123_client()
    if client is None:
        return [], None, None
    try:
        from datetime import date
        raw = client.rank_ranks({
            "rankingSystem": ranking_id,
            "asOfDt": date.today().isoformat(),
            "universe": universe,
            "nodeDetails": "factor",
        })
        quota = raw.get("quotaRemaining") if isinstance(raw, dict) else None
        p123_tickers = raw.get("tickers", [])
        yf_tickers = [_p123_to_yfinance(t) for t in p123_tickers]

        # Extract composite node data (skip index 0 which is the root/Overall)
        nodes = raw.get("nodes") if isinstance(raw, dict) else None
        nodes_data = None
        if nodes and "names" in nodes and "ranks" in nodes:
            ids = nodes.get("ids", [])[1:]
            parents = nodes.get("parents", [])[1:]
            names = nodes["names"][1:]
            weights = nodes["weights"][1:]
            scores = {}
            for i, t in enumerate(yf_tickers):
                if i < len(nodes["ranks"]):
                    scores[t] = [nodes["ranks"][i][j] for j in range(1, len(nodes["names"]))]
            nodes_data = {
                "ids": ids,
                "parents": parents,
                "names": names,
                "weights": weights,
                "scores": scores,
            }

        return yf_tickers, nodes_data, quota
    except Exception:
        return [], None, None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_strategy_details(strategy_id: int) -> dict:
    """Fetch strategy metadata from P123."""
    client = get_p123_client()
    if client is None:
        return {}
    try:
        return client.strategy(strategy_id)
    except Exception:
        return {}


# ---- Rebalance (Trader) ----
# NOT cached — rebalance data must always be fresh before committing.


def fetch_rebalance_recs(strategy_id: int) -> dict:
    """Fetch rebalance recommendations for a strategy.

    Returns dict with keys: ranks, op, recs, quotaRemaining.
    """
    client = get_p123_client()
    if client is None:
        raise RuntimeError("P123 API not configured")
    return client.strategy_rebalance(strategy_id=strategy_id, params={})


def commit_rebalance(strategy_id: int, ranks: list, trans: list, op=None) -> dict:
    """Commit rebalance transactions for a strategy.

    Args:
        strategy_id: P123 strategy ID
        ranks: Original ranks list from fetch_rebalance_recs
        trans: List of modified rec dicts (with updated shares)
        op: Optional op token from fetch_rebalance_recs
    """
    client = get_p123_client()
    if client is None:
        raise RuntimeError("P123 API not configured")
    params = {"ranks": ranks, "trans": trans}
    if op:
        params["op"] = op
    return client.strategy_rebalance_commit(strategy_id=strategy_id, params=params)
