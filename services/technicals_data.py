"""Technicals data — Sector Rotation (RRG), Correlation Matrix, AC Regime, RS Ranking, Stage Analysis."""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from utils.constants import SECTOR_ETFS

_TTL_12H = 43200

# ---------------------------------------------------------------------------
# Sector Rotation (Relative Rotation Graph)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def _fetch_rrg_weekly_prices() -> dict | None:
    """Download weekly sector + SPY prices (cached, independent of trail length)."""
    tickers = list(SECTOR_ETFS.keys()) + ["SPY"]
    try:
        raw = yf.download(tickers, period="2y", interval="1wk",
                          progress=False, auto_adjust=True, timeout=120)
    except Exception:
        return None

    if raw.empty:
        return None

    close = raw["Close"]
    if isinstance(close, pd.Series):
        return None

    spy = close.get("SPY")
    if spy is None or spy.dropna().empty:
        return None

    return {"close": close, "spy": spy}


def fetch_rrg_data(trail_weeks: int = 4) -> dict:
    """Compute Relative Rotation Graph data for sector ETFs.

    Returns dict with:
      - current: DataFrame (ticker, name, rs_ratio, rs_momentum, ret_1m, ret_3m, quadrant)
      - trails: dict of {ticker: [(rs_ratio, rs_momentum), ...]} for trail lines
    """
    prices = _fetch_rrg_weekly_prices()
    if prices is None:
        return {}

    close = prices["close"]
    spy = prices["spy"]

    rows = []
    trails = {}

    for ticker, name in SECTOR_ETFS.items():
        if ticker not in close.columns:
            continue
        sector = close[ticker].dropna()
        if len(sector) < 60:
            continue

        # Align with SPY
        aligned = pd.DataFrame({"Sector": sector, "SPY": spy}).dropna()
        if len(aligned) < 60:
            continue

        # RS line: sector / SPY * 100
        rs = aligned["Sector"] / aligned["SPY"] * 100

        # RS-Ratio: RS / 52-week MA of RS * 100
        rs_ma = rs.rolling(52, min_periods=26).mean()
        rs_ratio = rs / rs_ma * 100

        # RS-Momentum: RS-Ratio / RS-Ratio.shift(trail_weeks) * 100
        rs_momentum = rs_ratio / rs_ratio.shift(trail_weeks) * 100

        # Current values
        current_ratio = rs_ratio.iloc[-1]
        current_momentum = rs_momentum.iloc[-1]

        if pd.isna(current_ratio) or pd.isna(current_momentum):
            continue

        # Returns
        prices_col = aligned["Sector"]
        ret_1m = (prices_col.iloc[-1] / prices_col.iloc[-4] - 1) * 100 if len(prices_col) > 4 else 0
        ret_3m = (prices_col.iloc[-1] / prices_col.iloc[-13] - 1) * 100 if len(prices_col) > 13 else 0

        # Quadrant
        if current_ratio >= 100 and current_momentum >= 100:
            quadrant = "Leading"
        elif current_ratio >= 100 and current_momentum < 100:
            quadrant = "Weakening"
        elif current_ratio < 100 and current_momentum < 100:
            quadrant = "Lagging"
        else:
            quadrant = "Improving"

        rows.append({
            "Ticker": ticker,
            "Name": name,
            "RS_Ratio": round(current_ratio, 2),
            "RS_Momentum": round(current_momentum, 2),
            "Ret_1M": round(ret_1m, 1),
            "Ret_3M": round(ret_3m, 1),
            "Quadrant": quadrant,
        })

        # Trail: last N+1 weeks of coordinates
        trail_pts = []
        for i in range(trail_weeks + 1):
            idx = -(trail_weeks + 1 - i)
            if abs(idx) <= len(rs_ratio) and abs(idx) <= len(rs_momentum):
                r = rs_ratio.iloc[idx]
                m = rs_momentum.iloc[idx]
                if not pd.isna(r) and not pd.isna(m):
                    trail_pts.append({"RS_Ratio": round(r, 2), "RS_Momentum": round(m, 2)})
        trails[ticker] = trail_pts

    if not rows:
        return {}

    return {
        "current": pd.DataFrame(rows),
        "trails": trails,
    }


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_rrg_backtest_data() -> dict:
    """Fetch weekly sector prices + compute weekly RRG quadrants for backtesting.

    Returns dict with:
      - prices: DataFrame of weekly close prices for all sectors + SPY
      - quadrants: DataFrame with Date index, one column per sector containing quadrant string
    """
    tickers = list(SECTOR_ETFS.keys()) + ["SPY"]
    try:
        raw = yf.download(tickers, period="10y", interval="1wk",
                          progress=False, auto_adjust=True, timeout=120)
    except Exception:
        return {}

    if raw.empty:
        return {}

    close = raw["Close"]
    if isinstance(close, pd.Series):
        return {}

    spy = close.get("SPY")
    if spy is None:
        return {}

    # Compute weekly quadrants, RS-Ratio, and RS-Momentum for each sector
    quadrants = pd.DataFrame(index=close.index)
    rs_ratios = pd.DataFrame(index=close.index)
    rs_momentums = pd.DataFrame(index=close.index)
    trail = 4

    for ticker in SECTOR_ETFS:
        if ticker not in close.columns:
            continue
        sector = close[ticker]
        aligned = pd.DataFrame({"Sector": sector, "SPY": spy}).dropna()
        if len(aligned) < 60:
            continue

        rs = aligned["Sector"] / aligned["SPY"] * 100
        rs_ma = rs.rolling(52, min_periods=26).mean()
        rs_ratio = rs / rs_ma * 100
        rs_momentum = rs_ratio / rs_ratio.shift(trail) * 100

        rs_ratios[ticker] = rs_ratio
        rs_momentums[ticker] = rs_momentum

        # Classify each week
        q = pd.Series(index=rs_ratio.index, dtype=str)
        for i in range(len(rs_ratio)):
            r = rs_ratio.iloc[i]
            m = rs_momentum.iloc[i]
            if pd.isna(r) or pd.isna(m):
                q.iloc[i] = ""
            elif r >= 100 and m >= 100:
                q.iloc[i] = "Leading"
            elif r >= 100 and m < 100:
                q.iloc[i] = "Weakening"
            elif r < 100 and m < 100:
                q.iloc[i] = "Lagging"
            else:
                q.iloc[i] = "Improving"
        quadrants[ticker] = q

    return {
        "prices": close,
        "quadrants": quadrants,
        "rs_ratios": rs_ratios,
        "rs_momentums": rs_momentums,
    }


# ---------------------------------------------------------------------------
# Intermarket Correlation Matrix
# ---------------------------------------------------------------------------

CORR_ASSETS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq",
    "IWM": "Small Caps",
    "TLT": "Long Bonds",
    "GLD": "Gold",
    "USO": "Oil",
    "UUP": "US Dollar",
    "EEM": "EM Equities",
    "HYG": "High Yield",
    "VNQ": "Real Estate",
    "XLE": "Energy",
    "BTC-USD": "Bitcoin",
}


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_correlation_matrix(window: int = 60) -> dict:
    """Compute rolling correlation matrix for intermarket assets.

    Returns dict with:
      - matrix: correlation DataFrame
      - returns: daily returns DataFrame (for pair explorer)
      - labels: {ticker: display_name}
    """
    tickers = list(CORR_ASSETS.keys())
    try:
        raw = yf.download(tickers, period="10y", interval="1d",
                          progress=False, auto_adjust=True, timeout=120)
    except Exception:
        return {}

    if raw.empty:
        return {}

    close = raw["Close"]
    if isinstance(close, pd.Series):
        return {}

    # Rename columns to display names
    rename_map = {t: CORR_ASSETS.get(t, t) for t in close.columns}
    close = close.rename(columns=rename_map)

    # Forward-fill gaps (some assets have trading holidays on different days)
    close = close.ffill()

    returns = close.pct_change().dropna(how="all")
    if len(returns) < window:
        return {}

    # Latest window correlation
    latest = returns.iloc[-window:]
    matrix = latest.corr().round(2)

    return {
        "matrix": matrix,
        "returns": returns,
        "labels": {v: v for v in CORR_ASSETS.values()},
    }


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_pair_correlation(returns: pd.DataFrame, asset1: str, asset2: str,
                            window: int = 60) -> pd.DataFrame:
    """Compute rolling correlation between two assets."""
    if asset1 not in returns.columns or asset2 not in returns.columns:
        return pd.DataFrame()

    rolling_corr = returns[asset1].rolling(window).corr(returns[asset2])
    df = pd.DataFrame({"Date": rolling_corr.index, "Correlation": rolling_corr.values})
    df = df.dropna()
    return df


# ---------------------------------------------------------------------------
# Autocorrelation Regime Map (placeholder)
# ---------------------------------------------------------------------------

REGIME_ASSETS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq",
    "IWM": "Small Caps",
    "TLT": "Long Bonds",
    "GLD": "Gold",
    "USO": "Oil",
    "UUP": "US Dollar",
}


# ---------------------------------------------------------------------------
# Autocorrelation Regime Map
# ---------------------------------------------------------------------------

AC_REGIME_ASSETS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq",
    "IWM": "Small Caps",
    "TLT": "Long Bonds",
    "GLD": "Gold",
    "USO": "Oil",
    "UUP": "USD Index",
    "EEM": "EM Equities",
    "HYG": "High Yield",
    "BTC-USD": "Bitcoin",
    "XLE": "Energy",
    "VNQ": "Real Estate",
}

AC_LAGS = {"Daily (lag-1)": 1, "Weekly (lag-5)": 5, "Monthly (lag-21)": 21}


def _rolling_autocorr(returns: pd.Series, lag: int = 1, window: int = 60) -> pd.Series:
    """Rolling autocorrelation at given lag over a rolling window."""
    return returns.rolling(window).apply(
        lambda x: x.autocorr(lag=lag) if len(x) >= lag + 2 else np.nan,
        raw=False,
    )


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_ac_regime_data(window: int = 60,
                          custom_tickers: tuple | None = None) -> dict:
    """Fetch autocorrelation regime data for assets at all lags.

    Args:
        window: Rolling window for autocorrelation.
        custom_tickers: Optional tuple of ticker strings. If provided, uses these
                        instead of default AC_REGIME_ASSETS. Ticker is used as name.

    Returns dict with:
        'heatmap': {lag: DataFrame with assets as columns, dates as index}
        'current': DataFrame with columns Asset, AC(1), AC(5), AC(21), Regime
        'assets': dict of ticker -> name
    """
    if custom_tickers:
        tickers = list(custom_tickers)
        ticker_names = {t: t for t in tickers}
    else:
        tickers = list(AC_REGIME_ASSETS.keys())
        ticker_names = AC_REGIME_ASSETS

    try:
        if len(tickers) == 1:
            raw = yf.download(tickers[0], period="3y", interval="1d",
                              auto_adjust=True, progress=False, timeout=120)
            if raw.empty:
                return {}
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            raw = yf.download(tickers, period="3y", interval="1d",
                              auto_adjust=True, progress=False, timeout=120)
            if raw.empty:
                return {}
            close = raw["Close"]
    except Exception:
        return {}

    # Rename to friendly names
    rename_map = {t: ticker_names.get(t, t) for t in close.columns if t in ticker_names}
    close = close.rename(columns=rename_map)

    # Forward-fill gaps (some assets have missing days)
    close = close.ffill()
    returns = close.pct_change(fill_method=None).dropna(how="all")

    heatmap_data = {}
    current_rows = []

    for lag_label, lag_val in AC_LAGS.items():
        ac_df = pd.DataFrame(index=returns.index)
        for asset in returns.columns:
            r = returns[asset].dropna()
            if len(r) < window + lag_val:
                continue
            ac_series = _rolling_autocorr(r, lag=lag_val, window=window)
            ac_df[asset] = ac_series
        heatmap_data[lag_label] = ac_df.dropna(how="all")

    # Build current regime table
    for asset_name in returns.columns:
        row = {"Asset": asset_name}
        for lag_label, lag_val in AC_LAGS.items():
            ac_df = heatmap_data.get(lag_label, pd.DataFrame())
            if asset_name in ac_df.columns:
                last_val = ac_df[asset_name].dropna()
                row[lag_label] = round(float(last_val.iloc[-1]), 3) if not last_val.empty else None
            else:
                row[lag_label] = None

        # Regime classification based on lag-1 AC
        ac1 = row.get("Daily (lag-1)")
        if ac1 is not None:
            if ac1 > 0.1:
                row["Regime"] = "Trending"
            elif ac1 < -0.1:
                row["Regime"] = "Mean-Reverting"
            else:
                row["Regime"] = "Neutral"
        else:
            row["Regime"] = "N/A"
        current_rows.append(row)

    current_df = pd.DataFrame(current_rows)
    if not current_df.empty:
        current_df = current_df.sort_values("Daily (lag-1)", ascending=False, na_position="last")

    return {
        "heatmap": heatmap_data,
        "current": current_df,
        "assets": ticker_names,
        "close": close,
    }


# ---------------------------------------------------------------------------
# Relative Strength Ranking
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_rs_ranking(custom_tickers: tuple | None = None,
                      benchmark: str = "SPY") -> dict:
    """Compute relative strength ranking for a universe of stocks.

    Returns dict with:
        'table': DataFrame with Rank, Ticker, 1M/3M/6M/12M RS, Composite RS
        'rs_lines': {ticker: DataFrame with Date, RS_Line, MA13, MA26}
        'benchmark': benchmark ticker
    """
    if custom_tickers:
        tickers = list(custom_tickers)
    else:
        tickers = _get_sp100_tickers()

    # Ensure benchmark is included
    all_tickers = list(set(tickers + [benchmark]))

    try:
        raw = yf.download(all_tickers, period="2y", interval="1d",
                          auto_adjust=True, progress=False, timeout=120)
        if raw.empty:
            return {}
        if len(all_tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": all_tickers[0]})
        else:
            close = raw["Close"]
    except Exception:
        return {}

    if benchmark not in close.columns:
        return {}

    close = close.ffill().dropna(how="all")
    bench = close[benchmark]

    periods = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}
    rows = []

    for ticker in [c for c in close.columns if c != benchmark]:
        if close[ticker].isna().sum() > len(close) * 0.5:
            continue

        row = {"Ticker": ticker}
        has_data = True

        for label, days in periods.items():
            if len(close[ticker].dropna()) < days + 5:
                row[f"RS_{label}"] = None
                continue
            try:
                asset_ret = (close[ticker].iloc[-1] / close[ticker].iloc[-days] - 1) * 100
                bench_ret = (bench.iloc[-1] / bench.iloc[-days] - 1) * 100
                row[f"RS_{label}"] = round(asset_ret - bench_ret, 2)
                row[f"Abs_{label}"] = round(asset_ret, 2)
            except (IndexError, ZeroDivisionError):
                row[f"RS_{label}"] = None
                row[f"Abs_{label}"] = None

        rows.append(row)

    if not rows:
        return {}

    df = pd.DataFrame(rows)

    # Composite RS: weighted average of available periods
    weights = {"RS_1M": 0.2, "RS_3M": 0.3, "RS_6M": 0.3, "RS_12M": 0.2}
    df["Composite"] = 0.0
    total_weight = 0.0
    for col, w in weights.items():
        if col in df.columns:
            mask = df[col].notna()
            df.loc[mask, "Composite"] += df.loc[mask, col] * w
            total_weight = max(total_weight, w)  # at least one weight
    df["Composite"] = df["Composite"].round(2)
    df["Rank"] = df["Composite"].rank(ascending=False, method="min").astype(int)
    df = df.sort_values("Rank")

    # RS lines for chart (ticker/benchmark ratio, normalized to 100)
    rs_lines = {}
    for ticker in df["Ticker"].head(50):  # Pre-compute for top 50
        if ticker in close.columns:
            rs = close[ticker] / bench * 100
            rs = rs.dropna()
            if len(rs) > 26 * 5:
                rs_df = pd.DataFrame({
                    "RS_Line": rs,
                    "MA13": rs.rolling(13 * 5).mean(),  # 13-week in daily
                    "MA26": rs.rolling(26 * 5).mean(),  # 26-week in daily
                })
                rs_df.index.name = "Date"
                rs_lines[ticker] = rs_df

    return {
        "table": df,
        "rs_lines": rs_lines,
        "benchmark": benchmark,
        "close": close,
    }


def _get_sp100_tickers() -> list[str]:
    """Get S&P 100 tickers from Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/S%26P_100", match="Symbol"
        )
        if tables:
            return tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception:
        pass
    # Fallback: top 30 large caps
    return [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "LLY",
        "JPM", "AVGO", "V", "UNH", "XOM", "MA", "PG", "JNJ", "COST",
        "HD", "ABBV", "WMT", "MRK", "CRM", "NFLX", "CVX", "BAC",
        "AMD", "KO", "PEP", "TMO", "LIN",
    ]


# ---------------------------------------------------------------------------
# Weinstein Stage Analysis
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    1: "Stage 1 — Basing",
    2: "Stage 2 — Advancing",
    3: "Stage 3 — Topping",
    4: "Stage 4 — Declining",
}

STAGE_COLORS = {
    1: "#6FA8DC",   # blue
    2: "#6AA84F",   # green
    3: "#E8A838",   # amber
    4: "#E06666",   # red
}


def _classify_stage(close: pd.Series, volume: pd.Series) -> dict:
    """Classify a single stock into Weinstein stage using weekly data.

    Returns dict with stage number, label, and supporting metrics.
    """
    if len(close) < 35 or close.isna().sum() > len(close) * 0.3:
        return None

    ma30w = close.rolling(30).mean()
    ma10w = close.rolling(10).mean()

    price_now = close.iloc[-1]
    ma30_now = ma30w.iloc[-1]
    ma10_now = ma10w.iloc[-1]

    if pd.isna(ma30_now) or pd.isna(price_now) or ma30_now == 0:
        return None

    # 30-week MA slope (5-week change)
    ma30_5wk_ago = ma30w.iloc[-5] if len(ma30w) >= 5 else ma30w.iloc[0]
    ma30_slope = (ma30_now - ma30_5wk_ago) / ma30_now * 100 if ma30_now != 0 else 0

    above_ma30 = price_now > ma30_now
    ma30_rising = ma30_slope > 0.5   # > 0.5% rise over 5 weeks
    ma30_falling = ma30_slope < -0.5

    # Volume trend: recent 4 weeks vs prior 9 weeks
    if len(volume) >= 13:
        vol_recent = volume.iloc[-4:].mean()
        vol_prior = volume.iloc[-13:-4].mean()
        vol_expanding = vol_recent > vol_prior * 1.1 if vol_prior > 0 else False
    else:
        vol_expanding = False

    # % above/below 30-week MA
    pct_from_ma30 = (price_now / ma30_now - 1) * 100

    # Classification
    if above_ma30 and ma30_rising:
        stage = 2
    elif above_ma30 and not ma30_rising:
        stage = 3
    elif not above_ma30 and ma30_falling:
        stage = 4
    else:
        stage = 1

    return {
        "Stage": stage,
        "Label": STAGE_LABELS[stage],
        "Price": round(price_now, 2),
        "MA30": round(ma30_now, 2),
        "Pct_from_MA30": round(pct_from_ma30, 1),
        "MA30_Slope": round(ma30_slope, 2),
        "Vol_Expanding": vol_expanding,
    }


@st.cache_data(ttl=_TTL_12H, show_spinner=False)
def fetch_stage_analysis(custom_tickers: tuple | None = None) -> dict:
    """Run Weinstein stage scanner on a universe of stocks.

    Returns dict with:
        'table': DataFrame with Ticker, Stage, Label, Price, MA30, etc.
        'distribution': {stage_num: count}
        'weekly_data': {ticker: DataFrame} for selected chart display
    """
    if custom_tickers:
        tickers = list(custom_tickers)
    else:
        tickers = _get_sp100_tickers()

    try:
        raw = yf.download(tickers, period="2y", interval="1wk",
                          auto_adjust=True, progress=False, timeout=180)
        if raw.empty:
            return {}
    except Exception:
        return {}

    if len(tickers) == 1:
        close_all = raw[["Close"]].rename(columns={"Close": tickers[0]})
        vol_all = raw[["Volume"]].rename(columns={"Volume": tickers[0]})
    else:
        close_all = raw["Close"]
        vol_all = raw["Volume"]

    rows = []
    weekly_data = {}

    for ticker in close_all.columns:
        close = close_all[ticker].dropna()
        volume = vol_all[ticker].dropna() if ticker in vol_all.columns else pd.Series(dtype=float)

        result = _classify_stage(close, volume)
        if result is None:
            continue

        result["Ticker"] = ticker
        rows.append(result)

        # Store weekly data for chart rendering (close + MA30 + volume)
        if len(close) >= 30:
            wk_df = pd.DataFrame({
                "Close": close,
                "MA30": close.rolling(30).mean(),
                "MA10": close.rolling(10).mean(),
                "Volume": volume.reindex(close.index) if not volume.empty else np.nan,
            })
            wk_df.index.name = "Date"
            weekly_data[ticker] = wk_df

    if not rows:
        return {}

    table = pd.DataFrame(rows)
    table = table.sort_values(["Stage", "Pct_from_MA30"], ascending=[True, False])

    # Distribution count
    distribution = {}
    for s in [1, 2, 3, 4]:
        distribution[s] = int((table["Stage"] == s).sum())

    return {
        "table": table,
        "distribution": distribution,
        "weekly_data": weekly_data,
        "total": len(table),
    }


# ---------------------------------------------------------------------------
# Relative Strength Ranking (placeholder)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Weinstein Stage Analysis (placeholder)
# ---------------------------------------------------------------------------
