"""Factor regime data pipeline — EWMA z-score regime classification for equity factor ETFs."""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

FACTOR_ETFS = {
    "Value": "VLUE",
    "Size": "SIZE",
    "Momentum": "MTUM",
    "Quality": "QUAL",
    "Growth": "IWF",
}
BENCHMARK = "SPY"

FACTOR_COLORS = {
    "Value": "#f59e0b",
    "Size": "#ef4444",
    "Momentum": "#3b82f6",
    "Quality": "#10b981",
    "Growth": "#8b5cf6",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_factor_regime_data(halflife: int = 90) -> dict:
    """Fetch factor ETF data, compute EWMA z-scores and regime classification.

    Returns dict with keys: zscore_df, regimes, active_returns_df, cumulative_active_df
    """
    tickers = list(FACTOR_ETFS.values()) + [BENCHMARK]
    try:
        raw = yf.download(tickers, start="2013-01-01", auto_adjust=True,
                          progress=False, timeout=30)
    except Exception:
        return {}

    if raw.empty:
        return {}

    close = raw["Close"]
    if isinstance(close, pd.Series):
        return {}

    # Daily returns
    returns = close.pct_change().dropna(how="all")

    # Active returns: factor return minus SPY return
    active = pd.DataFrame(index=returns.index)
    for name, etf in FACTOR_ETFS.items():
        if etf in returns.columns and BENCHMARK in returns.columns:
            active[name] = returns[etf] - returns[BENCHMARK]

    active = active.dropna(how="all")
    if active.empty:
        return {}

    # Step 2: EWMA trend of active returns
    ewma_trend = active.ewm(halflife=halflife, min_periods=max(halflife // 2, 30)).mean()

    # Step 3: Expanding-window z-score of the EWMA trend
    expanding_mean = ewma_trend.expanding(min_periods=60).mean()
    expanding_std = ewma_trend.expanding(min_periods=60).std()
    raw_zscore = (ewma_trend - expanding_mean) / expanding_std

    # Step 4: Second EWMA smoothing to reduce whipsaws
    smooth_halflife = max(halflife // 3, 10)
    smoothed_zscore = raw_zscore.ewm(halflife=smooth_halflife, min_periods=smooth_halflife).mean()
    smoothed_zscore = smoothed_zscore.dropna(how="all")

    if smoothed_zscore.empty:
        return {}

    # Step 5: Regime classification
    regime_df = (smoothed_zscore >= 0).astype(int)  # 1 = BULL, 0 = BEAR

    # Build regime summary for each factor
    regimes = {}
    for name in FACTOR_ETFS:
        if name not in smoothed_zscore.columns:
            continue
        col = smoothed_zscore[name].dropna()
        if col.empty:
            continue

        current_zscore = col.iloc[-1]
        current_regime = "BULL" if current_zscore >= 0 else "BEAR"

        # Count days in current regime
        regime_series = (col >= 0)
        current_val = regime_series.iloc[-1]
        days = 0
        for v in regime_series.iloc[::-1]:
            if v == current_val:
                days += 1
            else:
                break

        regimes[name] = {
            "etf": FACTOR_ETFS[name],
            "regime": current_regime,
            "zscore": round(current_zscore, 2),
            "days_in_regime": days,
        }

    # Cumulative active returns for backtest tab
    cumulative_active = (1 + active).cumprod() - 1

    # Statistics per factor
    stats = {}
    for name in FACTOR_ETFS:
        if name not in smoothed_zscore.columns:
            continue
        col = smoothed_zscore[name].dropna()
        regime_col = (col >= 0)

        # Count regime changes
        changes = (regime_col != regime_col.shift()).sum() - 1
        bull_days = regime_col.sum()
        bear_days = len(regime_col) - bull_days

        stats[name] = {
            "bull_days": int(bull_days),
            "bear_days": int(bear_days),
            "regime_changes": int(changes),
            "avg_regime_days": int(len(regime_col) / max(changes, 1)),
            "current_zscore": round(col.iloc[-1], 2),
            "min_zscore": round(col.min(), 2),
            "max_zscore": round(col.max(), 2),
        }

    # ---- Volume Conviction Analysis ----
    volume = raw.get("Volume")
    volume_conviction = {}
    if volume is not None and isinstance(volume, pd.DataFrame):
        for name, etf in FACTOR_ETFS.items():
            if etf not in volume.columns:
                continue
            vol = volume[etf].dropna()
            if len(vol) < 30:
                continue

            # Use previous completed day (not today's partial volume)
            prev_vol = vol.iloc[-2] if len(vol) >= 2 else vol.iloc[-1]

            # Averages based on completed days (exclude today)
            completed = vol.iloc[:-1] if len(vol) > 1 else vol
            avg_20d = completed.iloc[-20:].mean()
            avg_60d = completed.iloc[-60:].mean() if len(completed) >= 60 else avg_20d
            std_20d = completed.iloc[-20:].std()

            # Relative volume — previous completed day vs 20-day average
            rel_vol = prev_vol / avg_20d if avg_20d > 0 else 1.0

            # Volume z-score — how unusual previous day's volume was
            vol_zscore = ((prev_vol - avg_20d) / std_20d) if std_20d > 0 else 0.0

            # 5-day average relative volume (completed days, smoother signal)
            avg_5d_vol = completed.iloc[-5:].mean()
            rel_vol_5d = avg_5d_vol / avg_60d if avg_60d > 0 else 1.0

            # Compute percentile-based thresholds from this ETF's own history
            # (rolling 20d/60d relative volume over all completed days)
            if len(completed) >= 120:
                hist_rel = completed.rolling(20).mean() / completed.rolling(60).mean()
                hist_rel = hist_rel.dropna()
                p25 = float(hist_rel.quantile(0.25))
                p75 = float(hist_rel.quantile(0.75))
                p90 = float(hist_rel.quantile(0.90))
            else:
                p25, p75, p90 = 0.7, 1.2, 1.5

            # Conviction assessment (based on Lee & Swaminathan 2000):
            # Low volume during regime shift = more persistent (higher conviction)
            # High volume = potential overreaction
            regime_info = regimes.get(name, {})
            days_in_regime = regime_info.get("days_in_regime", 999)
            recent_shift = days_in_regime <= 30  # regime changed in last 30 days

            if recent_shift:
                if rel_vol_5d <= p25:
                    conviction = "High"
                    conviction_note = f"Low-volume shift (below 25th pct) — historically more persistent"
                elif rel_vol_5d >= p90:
                    conviction = "Caution"
                    conviction_note = f"High-volume shift (above 90th pct) — may signal overreaction"
                elif rel_vol_5d >= p75:
                    conviction = "Elevated"
                    conviction_note = f"Above-average volume during shift — monitor for reversal"
                else:
                    conviction = "Neutral"
                    conviction_note = "Normal volume during regime shift"
            else:
                if rel_vol_5d >= p90:
                    conviction = "Watch"
                    conviction_note = f"Unusual volume (above 90th pct) — potential regime change"
                elif rel_vol_5d >= p75:
                    conviction = "Active"
                    conviction_note = f"Above-average volume — increased institutional activity"
                elif rel_vol_5d <= p25:
                    conviction = "Quiet"
                    conviction_note = f"Below-average volume — low activity, regime stable"
                else:
                    conviction = "Steady"
                    conviction_note = "Established regime with normal volume"

            volume_conviction[name] = {
                "etf": etf,
                "current_volume": int(prev_vol),
                "avg_20d": int(avg_20d),
                "rel_volume": round(rel_vol, 2),
                "rel_volume_5d": round(rel_vol_5d, 2),
                "vol_zscore": round(vol_zscore, 2),
                "conviction": conviction,
                "conviction_note": conviction_note,
                "recent_shift": recent_shift,
            }

    # Rolling relative volume for chart (20-day vol / 60-day vol, smoothed)
    rel_vol_df = pd.DataFrame(index=close.index)
    if volume is not None and isinstance(volume, pd.DataFrame):
        for name, etf in FACTOR_ETFS.items():
            if etf not in volume.columns:
                continue
            vol = volume[etf].dropna()
            if len(vol) < 60:
                continue
            rolling_20 = vol.rolling(20).mean()
            rolling_60 = vol.rolling(60).mean()
            rel = rolling_20 / rolling_60
            # Smooth with 10-day EWMA to reduce noise
            rel_vol_df[name] = rel.ewm(halflife=10).mean()
    rel_vol_df = rel_vol_df.dropna(how="all")

    return {
        "zscore_df": smoothed_zscore,
        "regimes": regimes,
        "active_returns_df": active,
        "cumulative_active_df": cumulative_active,
        "regime_df": regime_df,
        "stats": stats,
        "volume_conviction": volume_conviction,
        "rel_vol_df": rel_vol_df,
    }
