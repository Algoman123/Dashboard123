"""FRED API data fetching for the Macro dashboard."""

import pandas as pd
import streamlit as st
from fredapi import Fred

# Cache TTLs (seconds) — macro data updates infrequently, so cache aggressively
_TTL_6H = 21600       # Yield curve snapshot (daily data)
_TTL_12H = 43200      # Fed policy, inflation, latest international data, ETF overlays
_TTL_24H = 86400      # Historical series (yield, CPI, CLI, M2, PE), monthly OECD data
_TTL_7D = 604800      # Recession periods (almost never changes)


# ---------------------------------------------------------------------------
# Yield Curve
# ---------------------------------------------------------------------------

YIELD_SERIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

MATURITY_ORDER = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "20Y", "30Y"]


@st.cache_data(ttl=_TTL_6H, show_spinner=False)
def fetch_yield_curve(api_key: str) -> dict:
    """Fetch latest yield for each maturity. Returns {maturity: yield_pct}."""
    fred = Fred(api_key=api_key)
    result = {}
    for label, series_id in YIELD_SERIES.items():
        try:
            s = fred.get_series(series_id)
            s = s.dropna()
            if not s.empty:
                result[label] = float(s.iloc[-1])
        except Exception:
            pass
    return result


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_yield_curve_on_date(api_key: str, date_str: str) -> dict:
    """Fetch yield curve for a specific date (YYYY-MM-DD). Returns nearest available."""
    fred = Fred(api_key=api_key)
    target = pd.Timestamp(date_str)
    start = (target - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    result = {}
    for label, series_id in YIELD_SERIES.items():
        try:
            s = fred.get_series(series_id, observation_start=start,
                                observation_end=date_str)
            s = s.dropna()
            if not s.empty:
                result[label] = float(s.iloc[-1])
        except Exception:
            pass
    return result


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_spread_history(api_key: str, start: str = "2015-01-01") -> pd.DataFrame:
    """Fetch 2Y, 5Y, 10Y, 30Y, 3M yield history and compute spreads."""
    fred = Fred(api_key=api_key)
    series_needed = {
        "3M": "DGS3MO", "2Y": "DGS2", "5Y": "DGS5",
        "10Y": "DGS10", "30Y": "DGS30",
    }
    frames = {}
    for label, sid in series_needed.items():
        try:
            s = fred.get_series(sid, observation_start=start)
            frames[label] = s.dropna()
        except Exception:
            pass

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames).dropna()
    df["2s10s"] = df["10Y"] - df["2Y"]
    df["3M10Y"] = df["10Y"] - df["3M"]
    df["5s30s"] = df["30Y"] - df["5Y"]
    df.index.name = "Date"
    return df


# ---------------------------------------------------------------------------
# International Yield Data (OECD via FRED)
# ---------------------------------------------------------------------------

INTERNATIONAL_YIELDS = {
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "CA": "Canada",
    "AU": "Australia",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "SE": "Sweden",
    "NO": "Norway",
    "NZ": "New Zealand",
    "KR": "South Korea",
    "PL": "Poland",
    "PT": "Portugal",
    "IE": "Ireland",
    "BE": "Belgium",
    "AT": "Austria",
    "FI": "Finland",
    "DK": "Denmark",
}

# Country → iShares/SPDR market ETF (for chart overlays)
COUNTRY_ETF = {
    "US": "SPY", "GB": "EWU", "DE": "EWG", "FR": "EWQ", "JP": "EWJ",
    "CA": "EWC", "AU": "EWA", "IT": "EWI", "ES": "EWP", "NL": "EWN",
    "CH": "EWL", "SE": "EWD", "NO": "ENOR", "NZ": "ENZL", "KR": "EWY",
    "PL": "EPOL", "PT": None, "IE": "EIRL", "BE": "EWK", "AT": "EWO",
    "FI": "EFNL", "DK": "EDEN",
}

# Country 2-letter → ISO3 for FRED recession indicators ({ISO3}RECDM)
_COUNTRY_ISO3 = {
    "US": "USA", "GB": "GBR", "DE": "DEU", "FR": "FRA", "JP": "JPN",
    "CA": "CAN", "AU": "AUS", "IT": "ITA", "ES": "ESP", "NL": "NLD",
    "CH": "CHE", "SE": "SWE", "NO": "NOR", "NZ": "NZL", "KR": "KOR",
    "PL": "POL", "PT": "PRT", "IE": "IRL", "BE": "BEL", "AT": "AUT",
    "FI": "FIN", "DK": "DNK",
}

# Country 2-letter → FRED CPI YoY series ID
# 659N = growth rate same period previous year (true YoY annual %)
_COUNTRY_CPI_SERIES = {
    cc: f"CPALTT01{cc}{'Q' if cc in ('AU', 'NZ') else 'M'}659N"
    for cc in INTERNATIONAL_YIELDS
}


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_international_yields(api_key: str) -> pd.DataFrame:
    """Fetch latest 10Y yield, 3M rate, and spread for all countries.
    Returns DataFrame with columns: code, country, 10Y, 3M, Spread, sorted by spread desc.
    """
    fred = Fred(api_key=api_key)
    rows = []
    for cc, name in INTERNATIONAL_YIELDS.items():
        y10 = _fetch_latest_value(fred, f"IRLTLT01{cc}M156N")
        r3m = _fetch_latest_value(fred, f"IR3TIB01{cc}M156N")

        # US: also try daily series for more current data
        if cc == "US":
            y10_daily = _fetch_latest_value(fred, "DGS10")
            r3m_daily = _fetch_latest_value(fred, "DGS3MO")
            if y10_daily is not None:
                y10 = y10_daily
            if r3m_daily is not None:
                r3m = r3m_daily

        if y10 is not None:
            spread = (y10 - r3m) if r3m is not None else None
            rows.append({
                "Code": cc,
                "Country": name,
                "10Y": round(y10, 2),
                "3M": round(r3m, 2) if r3m is not None else None,
                "Spread": round(spread, 2) if spread is not None else None,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values("Spread", ascending=False, na_position="last")
    return df.reset_index(drop=True)


def _fetch_latest_value(fred: Fred, series_id: str) -> float | None:
    """Fetch the latest non-NaN value from a FRED series."""
    try:
        s = fred.get_series(series_id)
        s = s.dropna()
        if not s.empty:
            return float(s.iloc[-1])
    except Exception:
        pass
    return None


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_country_yield_history(api_key: str, country_code: str,
                                 start: str = "2000-01-01") -> pd.DataFrame:
    """Fetch 10Y and 3M history for a specific country. Returns DataFrame with 10Y, 3M, Spread."""
    fred = Fred(api_key=api_key)
    frames = {}

    # For US, use daily series (more granular)
    if country_code == "US":
        series_map = {"10Y": "DGS10", "3M": "DGS3MO"}
    else:
        series_map = {
            "10Y": f"IRLTLT01{country_code}M156N",
            "3M": f"IR3TIB01{country_code}M156N",
        }

    for label, sid in series_map.items():
        try:
            s = fred.get_series(sid, observation_start=start)
            frames[label] = s.dropna()
        except Exception:
            pass

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames).dropna(how="all")
    if "10Y" in df.columns and "3M" in df.columns:
        df["Spread"] = df["10Y"] - df["3M"]
    df.index.name = "Date"
    return df


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_us_10y_history(api_key: str, start: str = "2000-01-01") -> pd.Series:
    """Fetch US 10Y yield history for comparison overlay."""
    fred = Fred(api_key=api_key)
    try:
        s = fred.get_series("DGS10", observation_start=start)
        s = s.dropna()
        s.name = "US 10Y"
        return s
    except Exception:
        return pd.Series(dtype=float, name="US 10Y")


@st.cache_data(ttl=_TTL_7D, show_spinner=False)
def fetch_country_recessions(api_key: str, country_code: str) -> list[tuple]:
    """Fetch recession periods for a specific country from OECD data on FRED.

    Returns list of (start_date, end_date) tuples, same format as fetch_recession_periods().
    Falls back to US NBER recessions if country data unavailable.
    """
    fred = Fred(api_key=api_key)

    # US: use the active NBER series
    if country_code == "US":
        return fetch_recession_periods(api_key)

    iso3 = _COUNTRY_ISO3.get(country_code)
    if not iso3:
        return fetch_recession_periods(api_key)  # fallback to US

    series_id = f"{iso3}RECDM"
    try:
        s = fred.get_series(series_id)
        s = s.dropna()
        if s.empty:
            return fetch_recession_periods(api_key)
    except Exception:
        return fetch_recession_periods(api_key)

    # Convert binary 0/1 series into (start, end) tuples
    periods = []
    in_recession = False
    start_dt = None
    for date, val in s.items():
        if val == 1 and not in_recession:
            start_dt = date
            in_recession = True
        elif val == 0 and in_recession:
            periods.append((start_dt, date))
            in_recession = False
    if in_recession and start_dt is not None:
        periods.append((start_dt, s.index[-1]))
    return periods


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_country_etf_history(api_key: str, country_code: str,
                               start: str = "2000-01-01") -> pd.Series:
    """Fetch market ETF price history for a country (for chart overlay)."""
    import yfinance as yf

    etf = COUNTRY_ETF.get(country_code)
    if not etf:
        return pd.Series(dtype=float)

    try:
        df = yf.download(etf, start=start, auto_adjust=True, progress=False, timeout=30)
        if df.empty:
            return pd.Series(dtype=float)
        close = df["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        close.name = etf
        return close.dropna()
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_international_cpi(api_key: str, country_code: str,
                             start: str = "2000-01-01") -> pd.DataFrame:
    """Fetch CPI YoY% for a country from OECD data on FRED.

    Returns DataFrame with column 'CPI_YoY'.
    """
    fred = Fred(api_key=api_key)
    series_id = _COUNTRY_CPI_SERIES.get(country_code)
    if not series_id:
        return pd.DataFrame()

    try:
        s = fred.get_series(series_id, observation_start=start)
        s = s.dropna()
        if s.empty:
            return pd.DataFrame()
        df = pd.DataFrame({"CPI_YoY": s})
        df.index.name = "Date"
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_international_cpi_latest(api_key: str) -> pd.DataFrame:
    """Fetch latest CPI YoY% for all countries.

    Returns DataFrame: Code, Country, CPI_YoY, sorted by CPI desc.
    """
    fred = Fred(api_key=api_key)
    rows = []
    for cc, name in INTERNATIONAL_YIELDS.items():
        series_id = _COUNTRY_CPI_SERIES.get(cc)
        if not series_id:
            continue
        val = _fetch_latest_value(fred, series_id)
        if val is not None:
            rows.append({"Code": cc, "Country": name, "CPI_YoY": round(val, 2)})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.sort_values("CPI_YoY", ascending=False)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# OECD Composite Leading Indicators (CLI) — proxy for PMI history
# ---------------------------------------------------------------------------

# Country 2-letter → FRED CLI series ID (Normalized)
_COUNTRY_CLI_SERIES = {
    cc: f"{_COUNTRY_ISO3.get(cc, cc)}LOLITONOSTSAM"
    for cc in INTERNATIONAL_YIELDS
    if cc in _COUNTRY_ISO3
}


@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_cli_history(api_key: str, country_code: str,
                      start: str = "2000-01-01") -> pd.DataFrame:
    """Fetch OECD Composite Leading Indicator history for a country.

    Returns DataFrame with column 'CLI'. Values centered around 100
    (above 100 = expansion, below 100 = contraction).
    """
    fred = Fred(api_key=api_key)
    iso3 = _COUNTRY_ISO3.get(country_code)
    if not iso3:
        return pd.DataFrame()

    series_id = f"{iso3}LOLITONOSTSAM"
    try:
        s = fred.get_series(series_id, observation_start=start)
        s = s.dropna()
        if s.empty:
            return pd.DataFrame()
        df = pd.DataFrame({"CLI": s})
        df.index.name = "Date"
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_cli_latest(api_key: str) -> pd.DataFrame:
    """Fetch latest OECD CLI for all countries.

    Returns DataFrame: Code, Country, CLI, sorted by CLI desc.
    """
    fred = Fred(api_key=api_key)
    rows = []
    for cc, name in INTERNATIONAL_YIELDS.items():
        iso3 = _COUNTRY_ISO3.get(cc)
        if not iso3:
            continue
        series_id = f"{iso3}LOLITONOSTSAM"
        val = _fetch_latest_value(fred, series_id)
        if val is not None:
            rows.append({"Code": cc, "Country": name, "CLI": round(val, 2)})

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.sort_values("CLI", ascending=False)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Recession periods (NBER) — for grey recession shading
# ---------------------------------------------------------------------------

# USREC is a binary series: 1 = recession, 0 = expansion
@st.cache_data(ttl=_TTL_7D, show_spinner=False)
def fetch_recession_periods(api_key: str, start: str = "1967-01-01") -> list[tuple]:
    """Fetch NBER recession periods. Returns list of (start_date, end_date) tuples."""
    fred = Fred(api_key=api_key)
    try:
        rec = fred.get_series("USREC", observation_start=start)
    except Exception:
        return []

    rec = rec.dropna()
    periods = []
    in_recession = False
    rec_start = None
    for dt, val in rec.items():
        if val == 1 and not in_recession:
            rec_start = dt
            in_recession = True
        elif val == 0 and in_recession:
            periods.append((rec_start, dt))
            in_recession = False
    if in_recession and rec_start is not None:
        periods.append((rec_start, rec.index[-1]))
    return periods


# ---------------------------------------------------------------------------
# Long-history yield spread (10Y-1Y) — back to 1967
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_10y1y_spread_history(api_key: str, start: str = "1967-01-01") -> pd.DataFrame:
    """Fetch 10Y and 1Y yields and compute 10Y-1Y spread. Long history for recession overlay."""
    fred = Fred(api_key=api_key)
    frames = {}
    for label, sid in [("10Y", "DGS10"), ("1Y", "DGS1")]:
        try:
            s = fred.get_series(sid, observation_start=start)
            frames[label] = s.dropna()
        except Exception:
            pass

    if len(frames) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(frames).dropna()
    df["10Y-1Y Spread"] = df["10Y"] - df["1Y"]
    df.index.name = "Date"
    return df


# ---------------------------------------------------------------------------
# S&P 500 Earnings Yield (inverse P/E) for yield vs PE chart
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_sp500_pe_data(api_key: str, start: str = "1990-01-01") -> pd.DataFrame:
    """Fetch 10Y Treasury yield and S&P 500 P/E ratio from FRED (Shiller PE via multpl proxy).
    Uses SP500 earnings yield estimate: FRED series for 10Y yield + yfinance for SPY P/E history.
    """
    fred = Fred(api_key=api_key)

    frames = {}
    # 10Y yield
    try:
        y10 = fred.get_series("DGS10", observation_start=start)
        frames["10Y Yield"] = y10.dropna()
    except Exception:
        pass

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames).dropna(how="all")
    df.index.name = "Date"
    return df


# ---------------------------------------------------------------------------
# Inflation
# ---------------------------------------------------------------------------

INFLATION_SERIES = {
    "CPI": "CPIAUCSL",
    "Core CPI": "CPILFESL",
    "PCE": "PCEPI",
    "Core PCE": "PCEPILFE",
    "PPI": "PPIACO",
    "5Y Breakeven": "T5YIE",
    "10Y Breakeven": "T10YIE",
}


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_inflation_data(api_key: str, start: str = "2015-01-01") -> pd.DataFrame:
    """Fetch inflation series and compute YoY % for index series."""
    fred = Fred(api_key=api_key)

    # Fetch monthly index series separately (need 12 months extra for YoY calc)
    start_dt = pd.Timestamp(start)
    early_start = (start_dt - pd.DateOffset(months=13)).strftime("%Y-%m-%d")

    monthly_series = {"CPI": "CPIAUCSL", "Core CPI": "CPILFESL", "PCE": "PCEPI",
                      "Core PCE": "PCEPILFE", "PPI": "PPIACO"}
    daily_series = {"5Y Breakeven": "T5YIE", "10Y Breakeven": "T10YIE"}

    # Fetch and compute YoY for monthly index series
    yoy_frames = {}
    for label, sid in monthly_series.items():
        try:
            s = fred.get_series(sid, observation_start=early_start)
            s = s.dropna()
            if not s.empty:
                yoy = s.pct_change(12) * 100
                yoy = yoy[yoy.index >= start_dt]
                yoy_frames[f"{label} YoY"] = yoy.dropna()
        except Exception:
            pass

    # Fetch daily breakeven series
    be_frames = {}
    for label, sid in daily_series.items():
        try:
            s = fred.get_series(sid, observation_start=start)
            be_frames[label] = s.dropna()
        except Exception:
            pass

    # Combine — keep monthly and daily separate then merge with ffill
    result = pd.DataFrame()
    if yoy_frames:
        monthly_df = pd.DataFrame(yoy_frames)
        result = monthly_df
    if be_frames:
        daily_df = pd.DataFrame(be_frames)
        if result.empty:
            result = daily_df
        else:
            # Resample monthly YoY to daily frequency to align with breakevens
            result = result.resample("D").ffill()
            result = result.join(daily_df, how="outer").ffill()

    result.index.name = "Date"
    return result.dropna(how="all")


# ---------------------------------------------------------------------------
# Fed Funds Rate
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_fed_rate_data(api_key: str, start: str = "2015-01-01") -> pd.DataFrame:
    """Fetch Fed Funds rate and target band."""
    fred = Fred(api_key=api_key)
    series = {
        "Fed Funds": "FEDFUNDS",
        "Upper Target": "DFEDTARU",
        "Lower Target": "DFEDTARL",
    }
    frames = {}
    for label, sid in series.items():
        try:
            s = fred.get_series(sid, observation_start=start)
            frames[label] = s.dropna()
        except Exception:
            pass

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames).ffill().dropna(how="all")
    df.index.name = "Date"
    return df


# ---------------------------------------------------------------------------
# M2 Money Supply
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_24H, show_spinner=False)
def fetch_m2_data(api_key: str, start: str = "2010-01-01") -> pd.DataFrame:
    """Fetch M2 money supply and compute YoY %."""
    fred = Fred(api_key=api_key)
    try:
        m2 = fred.get_series("M2SL", observation_start=start).dropna()
    except Exception:
        return pd.DataFrame()

    df = pd.DataFrame({"M2 (Trillions)": m2 / 1000})
    df["M2 YoY %"] = m2.pct_change(12) * 100
    df.index.name = "Date"
    return df.dropna(how="all")
