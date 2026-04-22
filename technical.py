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


def compute_ma(close: pd.Series, ma_type: str = "SMA", period: int = 20) -> pd.Series:
    """Compute SMA or EMA for a price series."""
    if ma_type == "EMA":
        return close.ewm(span=period, adjust=False).mean()
    return close.rolling(period).mean()   # SMA default


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
    use_ma_filter: bool = False,
    ma_type: str = "SMA",
    ma_period: int = 20,
) -> dict:
    """
    Check if WVF green bar fired in the last `lookback_days` sessions.
    Optionally checks whether latest close is above the chosen MA.

    Returns dict with keys:
      green (bool), days (int signal count), wvf, upper_band, range_high,
      above_ma (bool|None), last_close, last_ma, ma_label,
      wvf_data (full DataFrame for charting), error (str if failed)
    """
    min_rows = max(lb + bbl + 5, ma_period + 5)
    df = fetch_ohlcv(code, market, days=max(160, min_rows + 20))
    if df is None or len(df) < min_rows:
        return {"code": code, "green": False, "days": 0, "error": "insufficient data"}

    try:
        result = compute_wvf(df, pd_=pd_, bbl=bbl, mult=mult, lb=lb, ph=ph, pl=pl)
        valid = result.dropna(subset=["wvf", "upper_band", "range_high"])
        tail = valid.tail(lookback_days)
        green_count = int(tail["green"].sum())
        last = valid.iloc[-1]

        out = {
            "code": code,
            "green": green_count > 0,
            "days": green_count,
            "wvf": round(float(last["wvf"]), 2),
            "upper_band": round(float(last["upper_band"]), 2),
            "range_high": round(float(last["range_high"]), 2),
            "above_ma": None,
            "last_close": None,
            "last_ma": None,
            "ma_label": f"{ma_type}{ma_period}",
            "wvf_data": valid,
        }

        if use_ma_filter:
            ma_series = compute_ma(df["Close"], ma_type, ma_period)
            last_close = float(df["Close"].iloc[-1])
            last_ma_val = float(ma_series.dropna().iloc[-1])
            out["above_ma"] = last_close > last_ma_val
            out["last_close"] = round(last_close, 2)
            out["last_ma"] = round(last_ma_val, 2)

            # Attach MA to wvf_data for charting
            valid = valid.copy()
            valid["ma"] = ma_series.reindex(valid.index)
            out["wvf_data"] = valid

        return out
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
        # auto_adjust=False → raw unadjusted close prices (actual market price on that day)
        # auto_adjust=True would back-adjust for dividends, giving wrong historical prices
        raw = yf.download(tickers, start=str(start), end=str(end),
                          progress=False, auto_adjust=False)
        if raw.empty:
            return {}

        # With auto_adjust=False, yfinance returns both "Close" and "Adj Close"
        close = raw["Close"] if "Close" in raw.columns else raw

        prices: dict[str, float] = {}
        if isinstance(close, pd.DataFrame) and len(ticker_to_code) > 1:
            # yfinance 1.0+: multi-ticker → DataFrame with ticker names as columns
            for ticker, code in ticker_to_code.items():
                try:
                    col = close[ticker].dropna()
                    if not col.empty:
                        prices[code] = float(col.iloc[-1])
                except Exception:
                    pass
        else:
            # single ticker → Series
            code = list(ticker_to_code.values())[0]
            col = (close.dropna() if isinstance(close, pd.Series)
                   else close.iloc[:, 0].dropna())
            if not col.empty:
                prices[code] = float(col.iloc[-1])

        logger.info(f"Historical prices fetched: {len(prices)}/{len(stocks)} stocks")
        return prices

    except Exception as e:
        logger.warning(f"Batch historical price fetch failed: {e}")
        return {}


def fetch_institutional_flow(code: str, days: int = 5) -> dict | None:
    """
    Fetch 三大法人 net buy/sell (張) for the last `days` trading days via FinMind free API.

    Returns dict with keys:
      foreign (int), trust (int), dealer (int), total (int),
      dates (list[str]), rows (list[dict])   ← all in 張 (÷1000)
    Returns None on error.

    FinMind dataset: TaiwanStockInstitutionalInvestorsBuySell
    Names mapped: Foreign_Investor+Foreign_Dealer_Self → foreign
                  Investment_Trust                     → trust
                  Dealer_self+Dealer_Hedging           → dealer
    """
    from datetime import date as _date, timedelta
    try:
        import requests as _req
        import urllib3; urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        return None

    start = (_date.today() - timedelta(days=days * 2 + 7)).strftime("%Y-%m-%d")
    url = (
        f"https://api.finmindtrade.com/api/v4/data"
        f"?dataset=TaiwanStockInstitutionalInvestorsBuySell"
        f"&data_id={code}&start_date={start}"
    )
    try:
        r = _req.get(url, timeout=8, verify=False)
        j = r.json()
        if j.get("status") != 200 or not j.get("data"):
            return None

        df = pd.DataFrame(j["data"])
        df["net"] = df["buy"] - df["sell"]

        # Keep last `days` unique trading dates
        all_dates = sorted(df["date"].unique())[-days:]
        df = df[df["date"].isin(all_dates)]

        # Map category → big-three bucket
        _map = {
            "Foreign_Investor":   "foreign",
            "Foreign_Dealer_Self": "foreign",
            "Investment_Trust":   "trust",
            "Dealer_self":        "dealer",
            "Dealer_Hedging":     "dealer",
        }
        df["bucket"] = df["name"].map(_map)
        df = df.dropna(subset=["bucket"])

        agg = df.groupby("bucket")["net"].sum()
        foreign = int(agg.get("foreign", 0)) // 1000
        trust   = int(agg.get("trust",   0)) // 1000
        dealer  = int(agg.get("dealer",  0)) // 1000
        total   = foreign + trust + dealer

        # Daily breakdown for charting: pivot to date × bucket
        daily = (
            df.groupby(["date", "bucket"])["net"].sum()
            .unstack(fill_value=0)
            .rename(columns={"foreign": "外資", "trust": "投信", "dealer": "自營商"})
        )
        for col in ["外資", "投信", "自營商"]:
            if col not in daily.columns:
                daily[col] = 0
        daily = daily[["外資", "投信", "自營商"]].div(1000).astype(int)
        daily.index = pd.to_datetime(daily.index)
        daily["合計"] = daily.sum(axis=1)

        return {
            "foreign": foreign, "trust": trust, "dealer": dealer,
            "total": total, "days": len(all_dates),
            "latest_date": all_dates[-1] if all_dates else "",
            "daily": daily,   # DataFrame with columns 外資/投信/自營商/合計, index=date
        }
    except Exception as e:
        logger.warning(f"[{code}] FinMind institutional flow error: {e}")
        return None


def make_institutional_chart(flow: dict, code: str, name: str):
    """Build a Plotly grouped-bar chart of daily 三大法人 net buy/sell (張)."""
    import plotly.graph_objects as go

    daily: pd.DataFrame = flow["daily"]
    dates = daily.index

    # Terminal palette: FOREIGN=green, TRUST=cyan, DEALER=amber
    colors = {"外資": "#10B981", "投信": "#22D3EE", "自營商": "#FFB800"}
    _mono = "JetBrains Mono, ui-monospace, monospace"

    fig = go.Figure()
    for col, color in colors.items():
        vals = daily[col].tolist()
        bar_colors = [color if v >= 0 else "#EF4444" for v in vals]
        fig.add_trace(go.Bar(
            name=col,
            x=dates,
            y=vals,
            marker=dict(color=bar_colors, line=dict(width=0)),
            opacity=0.95,
        ))

    # Total line
    fig.add_trace(go.Scatter(
        name="合計",
        x=dates,
        y=daily["合計"].tolist(),
        mode="lines+markers",
        line=dict(color="#E5E7EB", width=1.5, dash="dot"),
        marker=dict(size=5, color="#E5E7EB",
                    line=dict(color="#0A0D12", width=1)),
    ))

    fig.add_hline(y=0, line_color="#1F2936", line_width=1)

    fig.update_layout(
        title=dict(
            text=f"  {code} · {name.upper()} / INST · FLOW · LOTS",
            font=dict(size=12, color="#9CA3AF", family=_mono),
            x=0, xanchor="left", y=0.96,
        ),
        barmode="group",
        plot_bgcolor="#0E1219",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9CA3AF", family=_mono),
        legend=dict(orientation="h", y=1.12, x=0,
                    font=dict(family=_mono, size=10, color="#9CA3AF"),
                    bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=44, r=20, t=55, b=32),
        height=260,
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)",
                   linecolor="#1F2936",
                   tickformat="%m/%d",
                   tickfont=dict(family=_mono, size=10, color="#9CA3AF")),
        yaxis=dict(title=dict(text="LOTS",
                              font=dict(family=_mono, size=10, color="#6B7280")),
                   gridcolor="rgba(255,255,255,0.04)",
                   linecolor="#1F2936",
                   tickfont=dict(family=_mono, size=10, color="#9CA3AF"),
                   zerolinecolor="#1F2936"),
        hoverlabel=dict(bgcolor="#0A0D12", bordercolor="#FFB800",
                        font=dict(family=_mono, color="#E5E7EB")),
    )
    return fig


def make_wvf_chart(result: dict, name: str, n_days: int = 60, flow: dict | None = None):
    """
    Build a Plotly figure of WVF (and optionally 三大法人) with shared x-axis.

    Rows:
      Row 1 (optional, when MA filter on): Price + MA
      Row N: WVF bars + Upper Band + Range High
      Row N+1 (when flow provided): 三大法人 grouped bars aligned to same x range
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    data: pd.DataFrame = result["wvf_data"].tail(n_days)
    has_ma  = "ma" in data.columns and data["ma"].notna().any()
    has_inst = flow is not None and flow.get("daily") is not None

    # Build daily institutional data aligned to WVF date range
    inst_daily: pd.DataFrame | None = None
    if has_inst:
        inst_daily = flow["daily"].copy()
        inst_daily.index = pd.to_datetime(inst_daily.index)
        # Restrict to WVF date range so x-axes align
        inst_daily = inst_daily[
            (inst_daily.index >= data.index.min()) &
            (inst_daily.index <= data.index.max())
        ]
        if inst_daily.empty:
            has_inst = False

    # Determine subplot layout
    n_rows = (1 if has_ma else 0) + 1 + (1 if has_inst else 0)
    if n_rows == 1:
        fig = go.Figure()
        price_row = wvf_row = inst_row = None
    else:
        if has_ma and has_inst:
            heights = [0.30, 0.40, 0.30]
        elif has_ma:
            heights = [0.40, 0.60]
        else:
            heights = [0.55, 0.45]
        fig = make_subplots(
            rows=n_rows, cols=1, shared_xaxes=True,
            row_heights=heights, vertical_spacing=0.03,
        )
        price_row = 1 if has_ma else None
        wvf_row   = 2 if has_ma else 1
        inst_row  = n_rows if has_inst else None

    def _add(trace, row=None):
        if row is not None:
            fig.add_trace(trace, row=row, col=1)
        else:
            fig.add_trace(trace)

    _mono = "JetBrains Mono, ui-monospace, monospace"

    # ── Price + MA row ──
    if has_ma and price_row:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["Close"],
            line=dict(color="#E5E7EB", width=1.3), name="CLOSE",
        ), row=price_row, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["ma"],
            line=dict(color="#FFB800", width=1.8),
            name=result.get("ma_label", "MA").upper(),
        ), row=price_row, col=1)

    # ── WVF row ── (green fire / dim)
    colors = ["#10B981" if g else "#2B3542" for g in data["green"]]
    _add(go.Bar(x=data.index, y=data["wvf"],
                marker=dict(color=colors, line=dict(width=0)),
                name="WVF", opacity=0.95), wvf_row)
    _add(go.Scatter(x=data.index, y=data["upper_band"],
                    line=dict(color="#22D3EE", width=1.5), name="BB UPPER"), wvf_row)
    _add(go.Scatter(x=data.index, y=data["range_high"],
                    line=dict(color="#FFB800", width=1.5, dash="dot"),
                    name="RANGE HIGH"), wvf_row)

    # ── 三大法人 row ──
    if has_inst and inst_row and inst_daily is not None:
        _inst_colors = {"外資": "#10B981", "投信": "#22D3EE", "自營商": "#FFB800"}
        _inst_labels = {"外資": "FOREIGN", "投信": "TRUST", "自營商": "DEALER"}
        for col, base_color in _inst_colors.items():
            vals = inst_daily[col].tolist()
            bar_colors = [base_color if v >= 0 else "#EF4444" for v in vals]
            fig.add_trace(go.Bar(
                name=_inst_labels[col], x=inst_daily.index, y=vals,
                marker=dict(color=bar_colors, line=dict(width=0)),
                opacity=0.95,
            ), row=inst_row, col=1)
        fig.add_trace(go.Scatter(
            name="TOTAL", x=inst_daily.index, y=inst_daily["合計"].tolist(),
            mode="lines+markers",
            line=dict(color="#E5E7EB", width=1.2, dash="dot"),
            marker=dict(size=4, color="#E5E7EB"),
        ), row=inst_row, col=1)
        fig.add_hline(y=0, line_color="#1F2936",
                      line_width=1, row=inst_row, col=1)

    # ── Layout ──
    total_height = 260 + (120 if has_ma else 0) + (200 if has_inst else 0)
    _title_text = (
        f"  {result['code']} · {name.upper()} / WVF · SIGNAL"
        + (" + INST · FLOW" if has_inst else "")
    )
    layout = dict(
        title=dict(
            text=_title_text,
            font=dict(size=12, color="#9CA3AF", family=_mono),
            x=0, xanchor="left", y=0.98,
        ),
        barmode="group",
        plot_bgcolor="#0E1219",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9CA3AF", family=_mono),
        legend=dict(orientation="h", y=1.08, x=0,
                    font=dict(family=_mono, size=10, color="#9CA3AF"),
                    bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=52, r=20, t=60, b=32),
        height=total_height,
        showlegend=True,
        hoverlabel=dict(bgcolor="#0A0D12", bordercolor="#FFB800",
                        font=dict(family=_mono, color="#E5E7EB")),
    )
    # Axis styling — apply to all xaxes/yaxes
    axis_style = dict(
        gridcolor="rgba(255,255,255,0.04)",
        linecolor="#1F2936",
        zerolinecolor="#1F2936",
        tickfont=dict(family=_mono, size=10, color="#9CA3AF"),
        showgrid=True,
    )
    for i in range(1, n_rows + 1):
        suffix = "" if i == 1 else str(i)
        layout[f"xaxis{suffix}"] = {**axis_style, "tickformat": "%m/%d"}
        layout[f"yaxis{suffix}"] = {**axis_style}
    if wvf_row:
        layout[f"yaxis{'' if wvf_row == 1 else wvf_row}"]["title"] = dict(
            text="WVF", font=dict(family=_mono, size=10, color="#6B7280"))
    if has_ma and price_row:
        layout["yaxis"]["title"] = dict(
            text="PRICE", font=dict(family=_mono, size=10, color="#6B7280"))
    if has_inst and inst_row:
        layout[f"yaxis{inst_row}"]["title"] = dict(
            text="LOTS", font=dict(family=_mono, size=10, color="#6B7280"))

    fig.update_layout(**layout)
    return fig
