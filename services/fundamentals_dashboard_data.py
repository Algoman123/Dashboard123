"""Fundamentals Dashboard data — Earnings calendar, sector valuations, insider trades, dividends, analyst revisions, IPOs."""

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from datetime import date, timedelta

from utils.constants import SECTOR_ETFS

_TTL_1H = 3600
_TTL_6H = 21600
_TTL_12H = 43200

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_FMP_BASE = "https://financialmodelingprep.com/api"


def _finnhub_get(endpoint: str, key: str, params: dict | None = None, timeout: int = 15) -> dict | list | None:
    """Helper for Finnhub API calls."""
    url = f"{_FINNHUB_BASE}/{endpoint}"
    p = {"token": key}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fmp_get(endpoint: str, key: str, params: dict | None = None, timeout: int = 15) -> dict | list | None:
    """Helper for FMP API calls."""
    url = f"{_FMP_BASE}/{endpoint}"
    p = {"apikey": key}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Tab 1: Earnings Calendar & Surprise Tracker
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_earnings_calendar(finnhub_key: str, start: str, end: str) -> pd.DataFrame:
    """Fetch earnings calendar from Finnhub.

    Returns DataFrame with: date, symbol, epsEstimate, epsActual,
    revenueEstimate, revenueActual, hour
    """
    data = _finnhub_get("calendar/earnings", finnhub_key,
                         {"from": start, "to": end})
    if not data or "earningsCalendar" not in data:
        return pd.DataFrame()

    rows = data["earningsCalendar"]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Standardize column names
    rename = {
        "date": "Date",
        "symbol": "Ticker",
        "epsEstimate": "EPS_Est",
        "epsActual": "EPS_Actual",
        "revenueEstimate": "Rev_Est",
        "revenueActual": "Rev_Actual",
        "hour": "Time",
        "year": "Year",
        "quarter": "Quarter",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df.sort_values("Date")

    # Map time codes
    if "Time" in df.columns:
        time_map = {"bmo": "Before Open", "amc": "After Close", "dmh": "During Hours"}
        df["Time"] = df["Time"].map(time_map).fillna("")

    return df


@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_earnings_surprises(ticker: str, finnhub_key: str) -> pd.DataFrame:
    """Fetch EPS surprise history for a specific ticker from Finnhub.

    Returns DataFrame with: period, actual, estimate, surprise, surprisePercent
    """
    data = _finnhub_get("stock/earnings", finnhub_key, {"symbol": ticker})
    if not data or not isinstance(data, list):
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if df.empty:
        return df

    rename = {
        "period": "Period",
        "actual": "Actual",
        "estimate": "Estimate",
        "surprise": "Surprise",
        "surprisePercent": "Surprise_Pct",
        "symbol": "Ticker",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "Period" in df.columns:
        df["Period"] = pd.to_datetime(df["Period"], errors="coerce")
        df = df.dropna(subset=["Period"])
        df = df.sort_values("Period")

    return df.tail(8)  # Last 8 quarters


@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_earnings_calendar_yf(tickers: tuple) -> pd.DataFrame:
    """yfinance fallback — get upcoming earnings dates for portfolio tickers."""
    rows = []
    for ticker in tickers:
        if ticker.startswith("^"):
            continue
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar
            if cal is not None and (not cal.empty if hasattr(cal, 'empty') else bool(cal)):
                if isinstance(cal, pd.DataFrame):
                    # Some yfinance versions return a DataFrame
                    if "Earnings Date" in cal.columns:
                        for ed in cal["Earnings Date"]:
                            rows.append({"Date": ed, "Ticker": ticker, "Source": "yfinance"})
                    elif "Earnings Date" in cal.index:
                        val = cal.loc["Earnings Date"]
                        if hasattr(val, "__iter__"):
                            for v in val:
                                rows.append({"Date": v, "Ticker": ticker, "Source": "yfinance"})
                        else:
                            rows.append({"Date": val, "Ticker": ticker, "Source": "yfinance"})
                elif isinstance(cal, dict):
                    if "Earnings Date" in cal:
                        dates = cal["Earnings Date"]
                        if isinstance(dates, list):
                            for d in dates:
                                rows.append({"Date": d, "Ticker": ticker, "Source": "yfinance"})
                        else:
                            rows.append({"Date": dates, "Ticker": ticker, "Source": "yfinance"})
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date")
    return df


# ---------------------------------------------------------------------------
# Tab 2: Sector P/E & Valuation Dashboard
# ---------------------------------------------------------------------------


@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_sector_valuations() -> pd.DataFrame:
    """Fetch valuation metrics for all sector ETFs via yfinance.

    Returns DataFrame with: Ticker, Sector, Trailing_PE, Forward_PE, PEG, Price_to_Book,
    Dividend_Yield, Beta, 1Y_Return, Market_Cap
    """
    rows = []
    for ticker, sector in SECTOR_ETFS.items():
        try:
            info = yf.Ticker(ticker).info
            if not info:
                continue

            trailing_pe = info.get("trailingPE")
            pb = info.get("priceToBook")
            # Use trailingAnnualDividendYield (0-1 scale, consistent)
            div_yield_raw = info.get("trailingAnnualDividendYield")
            if div_yield_raw and div_yield_raw > 0:
                div_yield = div_yield_raw * 100
            else:
                div_yield_raw = info.get("dividendYield")
                if div_yield_raw:
                    div_yield = div_yield_raw if div_yield_raw > 1 else div_yield_raw * 100
                else:
                    div_yield = None
            beta = info.get("beta3Year") or info.get("beta")
            ytd_return = info.get("ytdReturn")
            expense_ratio = info.get("netExpenseRatio")
            yr1_change = info.get("fiftyTwoWeekChangePercent")
            yr3_avg = info.get("threeYearAverageReturn")
            yr5_avg = info.get("fiveYearAverageReturn")
            q3m_return = info.get("trailingThreeMonthReturns")

            rows.append({
                "Ticker": ticker,
                "Sector": sector,
                "Trailing_PE": round(trailing_pe, 1) if trailing_pe else None,
                "P/B": round(pb, 2) if pb else None,
                "Div_Yield": round(div_yield, 2) if div_yield else None,
                "Beta": round(beta, 2) if beta else None,
                "Expense": round(expense_ratio * 100, 2) if expense_ratio else None,
                "YTD": round(ytd_return, 1) if ytd_return else None,
                "3M": round(q3m_return, 1) if q3m_return else None,
                "1Y": round(yr1_change, 1) if yr1_change is not None else None,
                "3Y_Avg": round(yr3_avg * 100, 1) if yr3_avg else None,
                "5Y_Avg": round(yr5_avg * 100, 1) if yr5_avg else None,
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df.sort_values("Trailing_PE", ascending=True, na_position="last")


@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_sector_pe_fmp(fmp_key: str) -> pd.DataFrame:
    """Fetch sector P/E from FMP (more accurate, includes historical).

    Returns DataFrame with: Sector, PE, Date
    """
    today_str = date.today().isoformat()
    data = _fmp_get(f"v4/sector_price_earning_ratio",
                     fmp_key, {"date": today_str, "exchange": "NYSE"})
    if not data or not isinstance(data, list):
        return pd.DataFrame()

    rows = []
    for item in data:
        rows.append({
            "Sector": item.get("sector", ""),
            "PE": item.get("pe"),
            "Date": item.get("date", today_str),
        })

    return pd.DataFrame(rows).dropna(subset=["PE"])


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_sector_pe_history_yf() -> pd.DataFrame:
    """Approximate historical sector P/E by tracking ETF price relative to earnings.

    Uses 5 years of monthly price data for sector ETFs + SPY as reference.
    Returns DataFrame with Date index, sector columns with price values.
    """
    tickers = list(SECTOR_ETFS.keys()) + ["SPY"]
    try:
        raw = yf.download(tickers, period="5y", interval="1mo",
                          auto_adjust=True, progress=False, timeout=60)
        if raw.empty:
            return pd.DataFrame()
        close = raw["Close"]
        close = close.rename(columns=SECTOR_ETFS)
        close.index.name = "Date"
        return close
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_sector_earnings_growth() -> pd.DataFrame:
    """Fetch earnings growth estimates for sector ETFs.

    Returns DataFrame with: Ticker, Sector, EPS_Growth (estimated forward)
    """
    rows = []
    for ticker, sector in SECTOR_ETFS.items():
        try:
            info = yf.Ticker(ticker).info
            if not info:
                continue

            # Forward EPS growth approximation
            trailing_eps = info.get("trailingEps")
            forward_eps = info.get("forwardEps")

            if trailing_eps and forward_eps and trailing_eps > 0:
                eps_growth = (forward_eps / trailing_eps - 1) * 100
            else:
                eps_growth = None

            rows.append({
                "Ticker": ticker,
                "Sector": sector,
                "EPS_Growth": round(eps_growth, 1) if eps_growth else None,
                "Forward_PE": info.get("forwardPE"),
            })
        except Exception:
            continue

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Placeholder functions for future tabs
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tab 3: Insider Transactions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_insider_transactions(finnhub_key: str, symbol: str) -> pd.DataFrame:
    """Fetch insider transactions for a single ticker from Finnhub.

    Returns DataFrame with: filingDate, name, transactionDate, transactionCode,
    change, share, transactionPrice
    """
    url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={symbol}&token={finnhub_key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()

        rows = []
        for tx in data:
            code = tx.get("transactionCode", "")
            # P=Purchase, S=Sale, M=Exercise, A=Grant, G=Gift
            if code in ("P", "S", "M"):
                rows.append({
                    "Filing Date": tx.get("filingDate", ""),
                    "Date": tx.get("transactionDate", ""),
                    "Name": tx.get("name", ""),
                    "Type": {"P": "Purchase", "S": "Sale", "M": "Exercise"}.get(code, code),
                    "Shares": tx.get("change", 0),
                    "Price": tx.get("transactionPrice", 0),
                    "Value": abs(tx.get("change", 0)) * (tx.get("transactionPrice", 0) or 0),
                    "Source": "Finnhub/SEC",
                })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date", ascending=False)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_insider_summary(finnhub_key: str, symbol: str) -> dict:
    """Get insider buy/sell summary for a ticker.

    Returns dict with: total_buys, total_sells, buy_value, sell_value, net_value
    """
    df = fetch_insider_transactions(finnhub_key, symbol)
    if df.empty:
        return {}

    # Last 6 months
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=180)
    recent = df[df["Date"] >= cutoff] if "Date" in df.columns else df

    buys = recent[recent["Type"] == "Purchase"]
    sells = recent[recent["Type"] == "Sale"]

    return {
        "total_buys": len(buys),
        "total_sells": len(sells),
        "buy_value": buys["Value"].sum() if not buys.empty else 0,
        "sell_value": sells["Value"].sum() if not sells.empty else 0,
        "net_value": buys["Value"].sum() - sells["Value"].sum(),
    }


# ---------------------------------------------------------------------------
# Tab 4: Dividends
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_dividend_data(tickers: tuple) -> pd.DataFrame:
    """Fetch dividend metrics for a list of tickers via yfinance.

    Returns DataFrame with: Ticker, Div_Yield, Div_Rate, Payout_Ratio,
    Ex_Date, Frequency, 5Y_Growth
    """
    rows = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if not info:
                continue

            div_yield_raw = info.get("trailingAnnualDividendYield")
            div_yield = div_yield_raw * 100 if div_yield_raw and div_yield_raw > 0 else None
            div_rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
            payout = info.get("payoutRatio")
            ex_date = info.get("exDividendDate")

            if div_yield is None or div_yield <= 0:
                continue  # Skip non-dividend payers

            # Estimate frequency from dividend history
            divs = t.dividends
            freq = "—"
            if len(divs) >= 4:
                last_year = divs.last("1Y")
                if len(last_year) >= 10:
                    freq = "Monthly"
                elif len(last_year) >= 3:
                    freq = "Quarterly"
                elif len(last_year) >= 1:
                    freq = "Annual"

            # 5-year dividend growth
            growth_5y = None
            if len(divs) >= 20:
                try:
                    recent_annual = divs.last("1Y").sum()
                    older_annual = divs.iloc[:min(4, len(divs))].sum()
                    years = min(5, len(divs) // 4) if len(divs) >= 4 else 1
                    if older_annual > 0 and years > 0:
                        growth_5y = ((recent_annual / older_annual) ** (1 / years) - 1) * 100
                except Exception:
                    pass

            # Ex-date formatting
            ex_str = ""
            if ex_date:
                try:
                    from datetime import datetime
                    ex_dt = datetime.fromtimestamp(ex_date)
                    ex_str = ex_dt.strftime("%b %d, %Y")
                except Exception:
                    ex_str = str(ex_date)

            rows.append({
                "Ticker": ticker,
                "Name": info.get("shortName", ticker),
                "Div_Yield": round(div_yield, 2),
                "Div_Rate": round(div_rate, 2) if div_rate else None,
                "Payout": round(payout * 100, 1) if payout and payout < 5 else None,
                "Ex_Date": ex_str,
                "Frequency": freq,
                "Growth_5Y": round(growth_5y, 1) if growth_5y is not None else None,
                "Price": info.get("regularMarketPrice") or info.get("previousClose"),
                "Source": "yfinance",
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df.sort_values("Div_Yield", ascending=False)


# ---------------------------------------------------------------------------
# Tab 5: Analyst Revisions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_analyst_recommendations(finnhub_key: str, symbol: str) -> pd.DataFrame:
    """Fetch analyst recommendation trends from Finnhub.

    Returns DataFrame with: period, strongBuy, buy, hold, sell, strongSell
    """
    url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={finnhub_key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["period"] = pd.to_datetime(df["period"])
        return df.sort_values("period", ascending=False).head(12)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_analyst_upgrades(finnhub_key: str, symbol: str) -> pd.DataFrame:
    """Fetch recent analyst upgrade/downgrade actions from Finnhub.

    Returns DataFrame with: gradeDate, company, fromGrade, toGrade, action
    """
    url = f"https://finnhub.io/api/v1/stock/upgrade-downgrade?symbol={symbol}&token={finnhub_key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        if not data or not isinstance(data, list):
            return pd.DataFrame()

        rows = []
        for item in data[:30]:  # Last 30 actions
            rows.append({
                "Date": item.get("gradeDate", ""),
                "Firm": item.get("company", ""),
                "From": item.get("fromGrade", ""),
                "To": item.get("toGrade", ""),
                "Action": item.get("action", ""),
                "Source": "Finnhub",
            })

        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        return df.sort_values("Date", ascending=False)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_1H, show_spinner=False)
def fetch_price_target(finnhub_key: str, symbol: str) -> dict:
    """Fetch analyst price target consensus from Finnhub.

    Returns dict with: targetHigh, targetLow, targetMean, targetMedian, lastUpdated
    """
    url = f"https://finnhub.io/api/v1/stock/price-target?symbol={symbol}&token={finnhub_key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return {}
        return r.json()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Tab 6: IPO Calendar
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_ipo_calendar(finnhub_key: str, start: str, end: str) -> pd.DataFrame:
    """Fetch IPO calendar from Finnhub.

    Returns DataFrame with: date, symbol, name, exchange, price, numberOfShares,
    totalSharesValue, status
    """
    url = (f"https://finnhub.io/api/v1/calendar/ipo"
           f"?from={start}&to={end}&token={finnhub_key}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json().get("ipoCalendar", [])
        if not data:
            return pd.DataFrame()

        rows = []
        for item in data:
            shares_val = item.get("totalSharesValue", 0) or 0
            rows.append({
                "Date": item.get("date", ""),
                "Symbol": item.get("symbol", ""),
                "Company": item.get("name", ""),
                "Exchange": item.get("exchange", ""),
                "Price Range": item.get("price", ""),
                "Shares": item.get("numberOfShares", 0),
                "Value": shares_val,
                "Status": item.get("status", ""),
                "Source": "Finnhub",
            })

        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date", ascending=True)
        return df
    except Exception:
        return pd.DataFrame()
