"""Sentiment data fetching — Fear & Greed, market breadth, AAII, Reddit mentions."""

import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Cache TTLs
_TTL_12H = 43200
_TTL_24H = 86400

# ---------------------------------------------------------------------------
# Fear & Greed (CNN via fear-greed package)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_fear_greed() -> dict:
    """Fetch CNN Fear & Greed index data.

    Returns dict with keys: score, rating, timestamp, history, indicators.
    """
    try:
        import fear_greed
        data = fear_greed.get()
        if isinstance(data, dict) and "score" in data:
            return data
    except Exception:
        pass
    return {}


import json
import os

_FG_HISTORY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fg_history.json")


def _load_fg_history() -> pd.DataFrame:
    """Load stored Fear & Greed history from disk."""
    if not os.path.exists(_FG_HISTORY_PATH):
        return pd.DataFrame()
    try:
        with open(_FG_HISTORY_PATH, "r") as f:
            records = json.load(f)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["Date"] = pd.to_datetime(df["Date"])
        return df
    except Exception:
        return pd.DataFrame()


def _save_fg_history(df: pd.DataFrame):
    """Save Fear & Greed history to disk."""
    try:
        records = df.copy()
        records["Date"] = records["Date"].dt.strftime("%Y-%m-%d")
        records.to_json(_FG_HISTORY_PATH, orient="records", indent=2)
    except Exception:
        pass


# Clean data 2011-2023 (no fake 50s)
_GITHUB_FG_CLEAN = (
    "https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/main/"
    "fear-greed-2011-2023.csv"
)
# Updated daily 2011-present (has corrupted 50s in late 2020 - early 2021)
_GITHUB_FG_RECENT = (
    "https://raw.githubusercontent.com/jasonisdoing/fear-and-greed/main/"
    "data/cnn_fear_greed_historic_data.csv"
)


def _parse_fg_csv(url: str) -> pd.DataFrame:
    """Download and parse a Fear & Greed CSV from GitHub."""
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return pd.DataFrame()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.rename(columns={"Fear Greed": "Score"})
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce")
        df["Rating"] = df["Score"].apply(_score_to_rating)
        return df[["Date", "Score", "Rating"]].dropna()
    except Exception:
        return pd.DataFrame()


def _fetch_github_fg_history() -> pd.DataFrame:
    """Download historical Fear & Greed data (2011-present) from GitHub.

    Uses whit3rabbit (clean, 2011-2023) as base, then appends only
    post-2023 data from jasonisdoing (which has corrupted data in 2020-2021).
    """
    # Primary: clean dataset
    clean = _parse_fg_csv(_GITHUB_FG_CLEAN)

    # Recent: for dates after the clean dataset ends
    recent = _parse_fg_csv(_GITHUB_FG_RECENT)

    if not clean.empty and not recent.empty:
        clean_max = clean["Date"].max()
        # Only use recent data for dates after the clean dataset
        recent_new = recent[recent["Date"] > clean_max]
        combined = pd.concat([clean, recent_new], ignore_index=True)
        combined = combined.sort_values("Date").drop_duplicates(subset="Date", keep="first")
        return combined.reset_index(drop=True)
    elif not clean.empty:
        return clean
    elif not recent.empty:
        return recent

    return pd.DataFrame()


def _score_to_rating(score: float) -> str:
    if score <= 25:
        return "extreme fear"
    elif score <= 45:
        return "fear"
    elif score <= 55:
        return "neutral"
    elif score <= 75:
        return "greed"
    else:
        return "extreme greed"


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_fear_greed_history() -> pd.DataFrame:
    """Fetch Fear & Greed history, merging GitHub archive + CNN API + stored history.

    On first run: downloads 2011-2023 from GitHub, adds ~252 recent days from CNN.
    Subsequent runs: loads stored data, appends new CNN days.
    Returns DataFrame with columns: Date, Score, Rating.
    """
    # Load existing stored history
    stored = _load_fg_history()

    # If no stored history, seed from GitHub (2011-2023)
    if stored.empty:
        stored = _fetch_github_fg_history()

    # Fetch fresh data from CNN API (~252 recent days)
    fresh = pd.DataFrame()
    try:
        import fear_greed
        points = fear_greed.get_history()
        if points:
            rows = [
                {"Date": p.date, "Score": p.score, "Rating": p.rating}
                for p in points
            ]
            fresh = pd.DataFrame(rows)
            fresh["Date"] = pd.to_datetime(fresh["Date"], utc=True).dt.tz_localize(None)
            fresh["Date"] = fresh["Date"].dt.normalize()
    except Exception:
        pass

    # Merge: stored history + fresh data, dedup by date
    if not stored.empty and not fresh.empty:
        combined = pd.concat([stored, fresh], ignore_index=True)
    elif not stored.empty:
        combined = stored
    elif not fresh.empty:
        combined = fresh
    else:
        return pd.DataFrame()

    combined["Date"] = pd.to_datetime(combined["Date"])
    combined = combined.sort_values("Date").drop_duplicates(subset="Date", keep="last")
    combined = combined.reset_index(drop=True)

    # Save merged history back to disk
    _save_fg_history(combined)

    return combined


# ---------------------------------------------------------------------------
# Market Breadth (yfinance — S&P 500 sample)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def _get_sp500_tickers() -> list[str]:
    """Fetch current S&P 500 constituent tickers from Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )
        df = tables[0]
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        return [t.strip() for t in tickers if isinstance(t, str)]
    except Exception:
        # Fallback: return a broad sample
        return [
            "AAPL", "MSFT", "NVDA", "GOOG", "META", "AVGO", "ADBE", "CRM", "AMD", "INTC",
            "ORCL", "CSCO", "IBM", "TXN", "QCOM", "NOW", "INTU", "AMAT", "MU", "LRCX",
            "JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "C", "USB",
            "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
            "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "WMT", "LOW",
            "CAT", "BA", "HON", "UPS", "RTX", "GE", "DE", "LMT", "MMM", "UNP",
            "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES",
            "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA",
            "NEE", "DUK", "SO", "AEP", "D", "PLD", "AMT", "SPG", "LIN", "APD",
            "PG", "KO", "PEP", "PM", "CL", "MO", "GIS", "K", "HSY", "SJM",
        ]


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_breadth_data() -> dict:
    """Compute market breadth metrics for full S&P 500.

    Returns dict with: pct_above_20, pct_above_50, pct_above_200,
                        history_20, history_50, history_200, total_stocks.
    """
    tickers = _get_sp500_tickers()

    try:
        data = yf.download(
            tickers, period="1y", interval="1d",
            progress=False, auto_adjust=True, timeout=120,
            threads=True,
        )
    except Exception:
        return {}

    if data.empty:
        return {}

    close = data["Close"]
    if isinstance(close, pd.Series):
        return {}

    # Compute MAs
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    # Current % above MAs
    latest = close.iloc[-1]
    total = int(latest.notna().sum())

    def _pct_above(latest_prices, latest_ma):
        valid = latest_prices.notna() & latest_ma.notna()
        if valid.sum() == 0:
            return 0.0
        return round((latest_prices[valid] > latest_ma[valid]).sum() / valid.sum() * 100, 1)

    pct_20 = _pct_above(latest, ma20.iloc[-1])
    pct_50 = _pct_above(latest, ma50.iloc[-1])
    pct_200 = _pct_above(latest, ma200.iloc[-1])

    # Historical time series of % above MAs (daily, last 252 trading days)
    hist_20, hist_50, hist_200 = [], [], []
    start_idx = max(0, len(close) - 252)

    for i in range(start_idx, len(close)):
        row = close.iloc[i]
        date = close.index[i]

        for ma, hist in [(ma20, hist_20), (ma50, hist_50), (ma200, hist_200)]:
            row_ma = ma.iloc[i]
            valid = row.notna() & row_ma.notna()
            if valid.sum() > 0:
                pct = (row[valid] > row_ma[valid]).sum() / valid.sum() * 100
                hist.append({"Date": date, "Pct": round(pct, 1)})

    return {
        "pct_above_20": pct_20,
        "pct_above_50": pct_50,
        "pct_above_200": pct_200,
        "total_stocks": total,
        "history_20": pd.DataFrame(hist_20) if hist_20 else pd.DataFrame(),
        "history_50": pd.DataFrame(hist_50) if hist_50 else pd.DataFrame(),
        "history_200": pd.DataFrame(hist_200) if hist_200 else pd.DataFrame(),
    }


# ---------------------------------------------------------------------------
# AAII Investor Sentiment Survey
# ---------------------------------------------------------------------------

# Local XLS file (auto-downloaded from AAII website)
_AAII_LOCAL_XLS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aaii_sentiment.xls")
_AAII_XLS_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
_AAII_PAGE_URL = "https://www.aaii.com/sentimentsurvey/sent_results"
# GitHub fallback: full Bull/Bear/Neutral breakdown (1987 – June 2024)
_AAII_GITHUB_CSV = (
    "https://raw.githubusercontent.com/psinopoli/AAII-Sentiment/main/AAII_SENTIMENT_CSV.csv"
)


def download_aaii_xls() -> bool:
    """Download the latest AAII sentiment XLS from their website.

    Visits the survey page first to obtain session cookies, then downloads the XLS.
    Saves to aaii_sentiment.xls in the project folder.
    Returns True on success.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": _AAII_PAGE_URL,
        }
        session = requests.Session()
        # Visit the page to get session cookies
        session.get(_AAII_PAGE_URL, headers=headers, timeout=15)
        # Download the XLS with cookies
        resp = session.get(_AAII_XLS_URL, headers=headers, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 50000:
            with open(_AAII_LOCAL_XLS, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def _parse_aaii_xls(path_or_bytes) -> pd.DataFrame:
    """Parse AAII sentiment XLS file (header on row 2, data as 0-1 fractions)."""
    try:
        df = pd.read_excel(path_or_bytes, header=2)
        # Columns: 0=Date, 1=Bullish, 2=Neutral, 3=Bearish, ...
        df.columns = list(range(len(df.columns)))
        df = df.rename(columns={0: "Date", 1: "Bullish", 2: "Neutral", 3: "Bearish"})
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        for col in ["Bullish", "Neutral", "Bearish"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Bullish", "Bearish"])
        # Convert 0-1 fractions to percentages
        if df["Bullish"].max() <= 1.0:
            df["Bullish"] *= 100
            df["Neutral"] *= 100
            df["Bearish"] *= 100
        df["Spread"] = df["Bullish"] - df["Bearish"]
        return df[["Date", "Bullish", "Neutral", "Bearish", "Spread"]].dropna()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_aaii_sentiment() -> pd.DataFrame:
    """Fetch AAII sentiment survey data (1987-present).

    Primary: local XLS file (aaii_sentiment.xls, download from AAII website).
    Fallback: GitHub archive (psinopoli/AAII-Sentiment, 1987-Jun 2024).
    Returns DataFrame with columns: Date, Bullish, Neutral, Bearish, Spread.
    """
    # Primary: local XLS file
    if os.path.exists(_AAII_LOCAL_XLS):
        result = _parse_aaii_xls(_AAII_LOCAL_XLS)
        if len(result) > 100:
            return result.sort_values("Date").reset_index(drop=True)

    # Auto-download from AAII website if no local file
    if download_aaii_xls():
        result = _parse_aaii_xls(_AAII_LOCAL_XLS)
        if len(result) > 100:
            return result.sort_values("Date").reset_index(drop=True)

    # Fallback: GitHub CSV
    try:
        from io import StringIO
        resp = requests.get(_AAII_GITHUB_CSV, timeout=20)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            df.columns = [str(c).strip() for c in df.columns]
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])
            for col in ["Bullish", "Neutral", "Bearish"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                if df[col].max() <= 1.0:
                    df[col] = df[col] * 100
            df = df[df["Bullish"] <= 100]
            df["Spread"] = df["Bullish"] - df["Bearish"]
            result = df[["Date", "Bullish", "Neutral", "Bearish", "Spread"]].dropna()
            if len(result) > 100:
                return result.sort_values("Date").reset_index(drop=True)
    except Exception:
        pass

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Reddit / Social Mentions (WSB)
# ---------------------------------------------------------------------------

# Common words to exclude from ticker detection
_COMMON_WORDS = {
    "I", "A", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF",
    "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OH", "OK", "ON", "OR", "OUR",
    "SO", "TO", "UP", "US", "WE", "CEO", "CFO", "CTO", "IPO", "ETF", "GDP",
    "ATH", "DD", "DTE", "EPS", "FD", "FOMO", "FUD", "GG", "HODL", "LOL",
    "IMO", "ITM", "OTM", "PE", "PM", "PT", "RH", "SEC", "TD", "TL", "WSB",
    "YOY", "API", "USA", "ALL", "BIG", "BUY", "DIP", "FOR", "GET", "GOT",
    "HAS", "HAD", "HIS", "HOW", "LET", "MAY", "NEW", "NOT", "NOW", "OLD",
    "ONE", "OUT", "OWN", "PUT", "RUN", "SAY", "SET", "THE", "TOP", "TRY",
    "TWO", "WAR", "WAY", "WHO", "WHY", "WIN", "WON", "YET", "YOU", "ARE",
    "CAN", "DAY", "DID", "END", "FAR", "FEW", "HIT", "LOW", "MAN", "OUR",
    "RED", "SEE", "VERY", "JUST", "LIKE", "WILL", "CALL", "CASH", "COME",
    "DOWN", "EVEN", "EVER", "GOOD", "HAVE", "HERE", "HIGH", "HOLD", "HOPE",
    "IDEA", "INTO", "KEEP", "KNOW", "LAST", "LONG", "LOOK", "LOSS", "LOTS",
    "MADE", "MAKE", "MANY", "MORE", "MOST", "MUCH", "MUST", "NEED", "NEXT",
    "NICE", "ONLY", "OPEN", "OVER", "PAID", "PLAY", "POST", "REAL", "RISK",
    "SAFE", "SAID", "SAME", "SELL", "SEND", "SHOW", "SOME", "STOP", "SURE",
    "TAKE", "TELL", "THAN", "THAT", "THEM", "THEN", "THEY", "THIS", "TIME",
    "TURN", "VERY", "WANT", "WEEK", "WENT", "WERE", "WHAT", "WHEN", "WILL",
    "WITH", "WORK", "YEAR", "YOUR", "ZERO", "YOLO", "BEAR", "BULL", "PUMP",
    "DUMP", "GAIN", "MOON", "BONE",
}

# Known valid tickers (top traded) to validate against
_KNOWN_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOG", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "AVGO", "NFLX", "COST", "CRM", "ADBE", "INTC", "QCOM", "TXN", "AMAT",
    "MU", "LRCX", "MRVL", "KLAC", "SNPS", "CDNS", "ARM", "SMCI", "PLTR",
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "C",
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "BMY",
    "XOM", "CVX", "COP", "SLB", "EOG",
    "HD", "MCD", "NKE", "SBUX", "TGT", "WMT", "LOW",
    "CAT", "BA", "HON", "UPS", "RTX", "GE", "DE", "LMT",
    "DIS", "CMCSA", "VZ", "T", "TMUS",
    "NEE", "DUK", "SO", "PLD", "AMT",
    "PG", "KO", "PEP", "PM", "CL",
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "ARKK", "XLF", "XLE", "XLK",
    "SOFI", "RIVN", "LCID", "NIO", "MARA", "COIN", "HOOD", "RBLX", "SNAP",
    "GME", "AMC", "BBBY", "BB", "NOK", "WISH", "CLOV", "SPCE",
    "BABA", "JD", "PDD", "BILI",
    "V", "MA", "PYPL", "SQ", "SHOP",
}


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_wsb_mentions(limit: int = 100) -> pd.DataFrame:
    """Fetch and parse r/wallstreetbets for ticker mentions.

    Returns DataFrame: Ticker, Mentions, TotalScore, AvgScore.
    """
    url = f"https://www.reddit.com/r/wallstreetbets/hot.json?limit={limit}"
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Dashboard123/1.0 (market-dashboard)"
        })
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
    except Exception:
        return pd.DataFrame()

    posts = data.get("data", {}).get("children", [])
    if not posts:
        return pd.DataFrame()

    # Parse ticker mentions from titles and selftext
    ticker_pattern = re.compile(r'\b([A-Z]{1,5})\b')
    mentions = {}

    for post in posts:
        pdata = post.get("data", {})
        title = pdata.get("title", "")
        selftext = pdata.get("selftext", "")[:500]  # limit text length
        score = pdata.get("score", 0)

        text = f"{title} {selftext}"
        found_tickers = set(ticker_pattern.findall(text))

        for t in found_tickers:
            if t in _COMMON_WORDS:
                continue
            if t not in _KNOWN_TICKERS:
                continue
            if t not in mentions:
                mentions[t] = {"count": 0, "total_score": 0}
            mentions[t]["count"] += 1
            mentions[t]["total_score"] += score

    if not mentions:
        return pd.DataFrame()

    rows = [
        {
            "Ticker": t,
            "Mentions": m["count"],
            "TotalScore": m["total_score"],
            "AvgScore": round(m["total_score"] / m["count"]) if m["count"] > 0 else 0,
        }
        for t, m in mentions.items()
    ]

    df = pd.DataFrame(rows)
    df = df.sort_values("Mentions", ascending=False).reset_index(drop=True)
    return df
