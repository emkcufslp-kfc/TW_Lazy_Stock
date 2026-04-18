# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — 篩選規則引擎
======================================
實作三大核心規則：
1. 最近 10 個曆年每年都有股利
2. 目前殖利率 ≥ 使用者門檻
3. 平均 5 年殖利率 ≥ 使用者門檻
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime

# --- 時間基準 ---
CURRENT_YEAR = datetime.today().year  # 2026
LATEST_10_YEARS = list(range(CURRENT_YEAR - 10, CURRENT_YEAR))  # 2016–2025
LATEST_5_YEARS = list(range(CURRENT_YEAR - 5, CURRENT_YEAR))    # 2021–2025


def latest_10_calendar_years_dividend_ok(div_df: pd.DataFrame) -> bool:
    """檢查最近 10 個曆年是否每年都有股利（total_div > 0）。
    
    Parameters
    ----------
    div_df : pd.DataFrame
        必須包含 'year' 和 'total_div' 欄位。
    
    Returns
    -------
    bool
        True 表示 10 個曆年全數有發放股利。
    """
    target = set(LATEST_10_YEARS)
    # 針對每年加總 total_div（處理同年度多次除權息情形）
    tmp = div_df[div_df["year"].isin(target)].groupby("year", as_index=False)["total_div"].sum()
    # 必須 10 個年度全數存在
    if set(tmp["year"].tolist()) != target:
        return False
    # 每年 total_div 都必須 > 0
    return bool((tmp["total_div"] > 0).all())


def compute_metrics(div_df: pd.DataFrame, price: float) -> dict | None:
    """計算殖利率相關指標。
    
    Parameters
    ----------
    div_df : pd.DataFrame
        單一股票的股利明細，必須包含 'year', 'cash_div', 'stock_div', 'total_div'。
    price : float
        該股的當前收盤價。
    
    Returns
    -------
    dict or None
        包含殖利率指標的字典，若資料不足則回傳 None。
    """
    if div_df.empty or price is None or price <= 0:
        return None

    # 每年加總（處理季配息等情形）
    div_df = div_df.groupby("year", as_index=False)[["cash_div", "stock_div", "total_div"]].sum()
    div_df = div_df.sort_values("year").copy()

    # 找最近有發配的年度
    paid = div_df[div_df["total_div"] > 0].copy()
    if paid.empty:
        return None

    latest_paid_year = int(paid["year"].max())
    latest_paid_total_div = float(paid.loc[paid["year"] == latest_paid_year, "total_div"].sum())

    # 近 5 年必須全數存在且有發配
    last5 = div_df[div_df["year"].isin(LATEST_5_YEARS)].copy()
    if len(last5) < 5:
        return None
    if not (last5["total_div"] > 0).all():
        return None

    # --- 殖利率計算 ---
    # 目前殖利率 = 最新已發配年度總股利 / 現價 × 100
    current_yield = latest_paid_total_div / price
    # 平均 5 年殖利率 = 近 5 年總股利合計 / 5 / 現價 × 100
    avg_5y_yield = float(last5["total_div"].sum()) / 5.0 / price

    return {
        "latest_paid_year": latest_paid_year,
        "latest_paid_total_div": round(latest_paid_total_div, 4),
        "current_yield_pct": round(current_yield * 100, 2),
        "sum_5y_div": round(float(last5["total_div"].sum()), 4),
        "avg_5y_yield_pct": round(avg_5y_yield * 100, 2),
        "years_5y": ",".join(map(str, sorted(last5["year"].tolist()))),
        "years_10y": ",".join(map(str, LATEST_10_YEARS)),
        "pass_10y_rule": latest_10_calendar_years_dividend_ok(div_df),
    }
