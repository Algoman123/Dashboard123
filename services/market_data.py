import yfinance as yf
import pandas as pd
import streamlit as st


# ---- Technical indicator helpers (module-level for reuse) ----

def _compute_rsi(close_series: pd.Series, period: int = 14):
    """Wilder-smoothed RSI. Returns latest value or None."""
    if len(close_series) < period + 1:
        return None
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    last_loss = avg_loss.iloc[-1]
    last_loss = last_loss.item() if hasattr(last_loss, "item") else float(last_loss)
    if last_loss == 0:
        return 100.0
    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
    rs = rs.item() if hasattr(rs, "item") else float(rs)
    return round(100 - (100 / (1 + rs)), 1)


def _sma_distance(close_series: pd.Series, price: float, window: int):
    """Percentage distance of price from SMA. Returns None if not enough data."""
    if len(close_series) < window:
        return None
    sma = close_series.rolling(window=window).mean().iloc[-1]
    sma_val = sma.item() if hasattr(sma, "item") else float(sma)
    if sma_val == 0:
        return None
    return round((price - sma_val) / sma_val * 100, 2)


def _relative_volume(volume_series: pd.Series, window: int = 20):
    """Today's volume / 20-day average. Returns None if not enough data."""
    if len(volume_series) < window + 1:
        return None
    avg_vol = volume_series.iloc[-(window + 1):-1].mean()
    avg_val = avg_vol.item() if hasattr(avg_vol, "item") else float(avg_vol)
    if avg_val == 0:
        return None
    current = volume_series.iloc[-1]
    cur_val = current.item() if hasattr(current, "item") else float(current)
    return round(cur_val / avg_val, 2)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Batch download price data and compute return + indicator metrics for all tickers."""
    if not tickers:
        return pd.DataFrame()

    ticker_list = list(tickers)
    single = len(ticker_list) == 1

    try:
        data = yf.download(
            ticker_list,
            period="1y",
            interval="1d",
            threads=True,
            progress=False,
            auto_adjust=True,
            timeout=30,
        )
    except Exception:
        return pd.DataFrame()

    if data.empty:
        return pd.DataFrame()

    results = []
    for ticker in ticker_list:
        try:
            if single:
                close = data["Close"].dropna()
                volume = data["Volume"].dropna()
            else:
                close = data["Close"][ticker].dropna()
                volume = data["Volume"][ticker].dropna()

            if len(close) < 2:
                continue

            price = close.iloc[-1].item() if hasattr(close.iloc[-1], 'item') else float(close.iloc[-1])
            vol = volume.iloc[-1].item() if hasattr(volume.iloc[-1], 'item') else float(volume.iloc[-1])

            def pct(periods):
                if len(close) > periods:
                    val = close.iloc[-1 - periods]
                    prev = val.item() if hasattr(val, 'item') else float(val)
                    if prev != 0:
                        return round((price - prev) / prev * 100, 2)
                return None

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Daily": pct(1),
                "5D": pct(5),
                "1M": pct(21),
                "3M": pct(63),
                "1Y": pct(min(252, len(close) - 1)) if len(close) > 2 else None,
                "Volume": vol,
                # Technical indicators
                "RSI": _compute_rsi(close),
                "SMA20": _sma_distance(close, price, 20),
                "SMA50": _sma_distance(close, price, 50),
                "SMA200": _sma_distance(close, price, 200),
                "RVOL": _relative_volume(volume),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).set_index("Ticker")


def format_volume(vol):
    """Format volume as human-readable string."""
    if vol is None or pd.isna(vol):
        return "N/A"
    if vol >= 1_000_000_000:
        return f"{vol / 1_000_000_000:.1f}B"
    if vol >= 1_000_000:
        return f"{vol / 1_000_000:.1f}M"
    if vol >= 1_000:
        return f"{vol / 1_000:.1f}K"
    return str(int(vol))


def format_pct(val):
    """Format percentage with sign and color class."""
    if val is None or pd.isna(val):
        return "N/A", ""
    sign = "+" if val >= 0 else ""
    css_class = "positive" if val >= 0 else "negative"
    return f"{sign}{val:.2f}%", css_class
