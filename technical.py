# -*- coding: utf-8 -*-
"""
Williams VIX Fix indicator for Taiwan stocks.

Pine Script reference (CM_Williams_Vix_Fix):
  wvf = ((highest(close, pd) - low) / highest(close, pd)) * 100
  green bar: wvf >= upperBand  OR  wvf >= rangeHigh
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False
    logger.warning("yfinance not installed — WVF scan unavailable")


def _yahoo_ticker(code: str, market: str) -> str:
    return f"{code}.TW" if market == "TWSE" else f"{code}.TWO"


def fetch_ohlcv(code: str, market: str, days: int = 160) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data from Yahoo Finance for a Taiwan stock."""
    if not _HAS_YF:
        return None
    try:
        tk = yf.Ticker(_yahoo_ticker(code, market))
        df = tk.history(period=f"{days}d", auto_adjust=True)
        if df is None or df.empty:
            return None
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df[["Open", "High", "Low", "Close", "Volume"]].copy()
    except Exception as e:
        logger.warning(f"[{code}] yfinance error: {e}")
        return None


def compute_wvf(
    df: pd.DataFrame,
    pd_: int = 22,
    bbl: int = 20,
    mult: float = 2.0,
    lb: int = 50,
    ph: float = 0.85,
    pl: float = 1.01,
) -> pd.DataFrame:
    """
    Compute Williams VIX Fix and its signal columns.

    Returns DataFrame with columns:
      wvf, upper_band, mid_band, range_high, range_low, green
    """
    close = df["Close"]
    low = df["Low"]

    highest_close = close.rolling(pd_).max()
    wvf = ((highest_close - low) / highest_close) * 100

    mid = wvf.rolling(bbl).mean()
    std = wvf.rolling(bbl).std()
    upper_band = mid + mult * std

    range_high = wvf.rolling(lb).max() * ph
    range_low = wvf.rolling(lb).min() * pl

    green = (wvf >= upper_band) | (wvf >= range_high)

    out = df[["Close", "Low"]].copy()
    out["wvf"] = wvf
    out["mid_band"] = mid
    out["upper_band"] = upper_band
    out["range_high"] = range_high
    out["range_low"] = range_low
    out["green"] = green
    return out


def check_signal(
    code: str,
    market: str,
    lookback_days: int = 3,
    pd_: int = 22,
    bbl: int = 20,
    mult: float = 2.0,
    lb: int = 50,
    ph: float = 0.85,
    pl: float = 1.01,
) -> dict:
    """
    Check if WVF green bar fired in the last `lookback_days` sessions.

    Returns dict with keys:
      green (bool), days (int signal count), wvf, upper_band, range_high,
      wvf_data (full DataFrame for charting), error (str if failed)
    """
    min_rows = lb + bbl + 5
    df = fetch_ohlcv(code, market, days=max(160, min_rows + 20))
    if df is None or len(df) < min_rows:
        return {"code": code, "green": False, "days": 0, "error": "insufficient data"}

    try:
        result = compute_wvf(df, pd_=pd_, bbl=bbl, mult=mult, lb=lb, ph=ph, pl=pl)
        valid = result.dropna(subset=["wvf", "upper_band", "range_high"])
        tail = valid.tail(lookback_days)
        green_count = int(tail["green"].sum())
        last = valid.iloc[-1]
        return {
            "code": code,
            "green": green_count > 0,
            "days": green_count,
            "wvf": round(float(last["wvf"]), 2),
            "upper_band": round(float(last["upper_band"]), 2),
            "range_high": round(float(last["range_high"]), 2),
            "wvf_data": valid,
        }
    except Exception as e:
        logger.warning(f"[{code}] WVF compute error: {e}")
        return {"code": code, "green": False, "days": 0, "error": str(e)}


def get_historical_prices_batch(
    stocks: list[dict],
    target_date,
) -> dict[str, float]:
    """
    Fetch closing prices for multiple stocks on or just before target_date.

    Parameters
    ----------
    stocks : list of {"code": str, "market": "TWSE"|"TPEX"}
    target_date : datetime.date

    Returns
    -------
    dict mapping code -> closing price
    """
    if not _HAS_YF or not stocks:
        return {}

    from datetime import timedelta

    start = target_date - timedelta(days=7)
    end   = target_date + timedelta(days=1)

    ticker_to_code: dict[str, str] = {
        (f"{s['code']}.TW" if s.get("market") == "TWSE" else f"{s['code']}.TWO"): str(s["code"])
        for s in stocks
    }

    try:
        tickers = list(ticker_to_code.keys())
        raw = yf.download(tickers, start=str(start), end=str(end),
                          progress=False, auto_adjust=True)
        if raw.empty:
            return {}

        close = raw["Close"] if "Close" in raw.columns else raw

        prices: dict[str, float] = {}
        if hasattr(close.columns, "levels"):          # MultiIndex (multiple tickers)
            for ticker, code in ticker_to_code.items():
                try:
                    col = close[ticker].dropna()
                    if not col.empty:
                        prices[code] = float(col.iloc[-1])
                except Exception:
                    pass
        else:                                          # flat (single ticker)
            code = list(ticker_to_code.values())[0]
            col = close.dropna()
            if not col.empty:
                prices[code] = float(col.iloc[-1])

        logger.info(f"Historical prices fetched: {len(prices)}/{len(stocks)} stocks")
        return prices

    except Exception as e:
        logger.warning(f"Batch historical price fetch failed: {e}")
        return {}


def make_wvf_chart(result: dict, name: str, n_days: int = 60):
    """Build a Plotly figure of the WVF for the last n_days sessions."""
    import plotly.graph_objects as go

    data: pd.DataFrame = result["wvf_data"].tail(n_days)
    colors = ["#00D4AA" if g else "#4a5568" for g in data["green"]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=data.index, y=data["wvf"],
        marker_color=colors, name="WVF", opacity=0.9,
    ))
    fig.add_trace(go.Scatter(
        x=data.index, y=data["upper_band"],
        line=dict(color="#00B4D8", width=2), name="Upper Band",
    ))
    fig.add_trace(go.Scatter(
        x=data.index, y=data["range_high"],
        line=dict(color="orange", width=2, dash="dot"), name="Range High",
    ))

    fig.update_layout(
        title=dict(text=f"{result['code']} {name} — Williams VIX Fix", font=dict(size=14, color="#e0e0e0")),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(title="WVF", gridcolor="rgba(255,255,255,0.08)"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c0c8d4"),
        legend=dict(orientation="h", y=1.12, x=0),
        margin=dict(l=40, r=20, t=55, b=30),
        height=280,
        showlegend=True,
    )
    return fig
