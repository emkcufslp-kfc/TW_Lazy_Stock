# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — 資料建置腳本
======================================
執行此腳本以從官方資料源抓取資料，
產出 screened_dataset.csv 與 dividend_history.csv。

用法：
    python build_dataset.py
    python build_dataset.py --top 500    # 自訂前 N 名
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

import pandas as pd

from data_sources import (
    fetch_full_universe,
    build_all_dividend_history,
    ensure_data_dir,
)
from screening import compute_metrics, latest_10_calendar_years_dividend_ok

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def build(top_n: int = 300) -> tuple[pd.DataFrame, pd.DataFrame]:
    """主建置流程。
    
    Parameters
    ----------
    top_n : int
        取前 N 名市值股票。
    
    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (screened_dataset, dividend_history)
    """
    data_dir = ensure_data_dir()
    log_path = data_dir / "build_log.txt"

    # --- Step 1: 取得股票清單 ---
    logger.info(f"=== 步驟 1/4：取得前 {top_n} 名市值股票清單 ===")
    universe = fetch_full_universe(top_n=top_n)
    if universe.empty:
        logger.error("無法取得股票清單，建置中止")
        return pd.DataFrame(), pd.DataFrame()

    logger.info(f"取得 {len(universe)} 檔股票")

    # --- Step 2: 爬取股利歷史 ---
    logger.info("=== 步驟 2/4：爬取 Goodinfo.tw 股利歷史 ===")
    div_hist = build_all_dividend_history(
        universe,
        delay=1.5,
        log_path=log_path,
    )
    if div_hist.empty:
        logger.error("無法取得股利資料，建置中止")
        return pd.DataFrame(), pd.DataFrame()

    logger.info(f"取得 {len(div_hist)} 筆股利紀錄")

    # --- Step 3: 篩選通過 10 年規則的股票 ---
    logger.info("=== 步驟 3/4：執行篩選規則 ===")
    results = []

    for _, row in universe.iterrows():
        code = row["code"]
        name = row["name"]
        market = row["market"]
        price = row["price"]

        sub = div_hist[div_hist["code"] == code].copy()
        if sub.empty:
            continue

        # 檢查 10 年連續配股利規則
        if not latest_10_calendar_years_dividend_ok(sub):
            continue

        # 計算殖利率指標
        metrics = compute_metrics(sub, price)
        if metrics is None:
            continue

        results.append({
            "code": code,
            "name": name,
            "market": market,
            "price": price,
            **metrics,
        })

    screened = pd.DataFrame(results)

    if not screened.empty:
        screened = screened.sort_values(
            ["avg_5y_yield_pct", "current_yield_pct", "code"],
            ascending=[False, False, True],
        ).reset_index(drop=True)

    logger.info(f"通過篩選: {len(screened)} 檔股票")

    # --- Step 4: 輸出 CSV ---
    logger.info("=== 步驟 4/4：輸出 CSV ===")
    screened_path = data_dir / "screened_dataset.csv"
    div_path = data_dir / "dividend_history.csv"

    screened.to_csv(screened_path, index=False, encoding="utf-8-sig")
    div_hist.to_csv(div_path, index=False, encoding="utf-8-sig")

    # 追加建置摘要到 log
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"建置完成: {datetime.now().isoformat()}\n")
        f.write(f"股票清單總數: {len(universe)}\n")
        f.write(f"股利紀錄總數: {len(div_hist)}\n")
        f.write(f"通過篩選股票: {len(screened)}\n")
        f.write(f"輸出檔案:\n")
        f.write(f"  - {screened_path}\n")
        f.write(f"  - {div_path}\n")

    logger.info(f"✅ 建置完成！")
    logger.info(f"   已篩選: {screened_path} ({len(screened)} 檔)")
    logger.info(f"   股利明細: {div_path} ({len(div_hist)} 筆)")

    return screened, div_hist


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台股股利選股資料建置")
    parser.add_argument("--top", type=int, default=300, help="取前 N 名市值股票 (預設: 300)")
    args = parser.parse_args()

    build(top_n=args.top)
