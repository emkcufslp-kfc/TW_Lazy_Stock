# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — 資料建置腳本
======================================
執行此腳本以從官方資料源抓取資料，
產出 screened_dataset.csv 與 dividend_history.csv。

用法：
    python build_dataset.py
    python build_dataset.py --top 500              # 自訂前 N 名
    python build_dataset.py --source finmind       # 使用 FinMind API（需網路）
    python build_dataset.py --source finmind --token YOUR_TOKEN  # 含 API token（提升速限）

股利資料來源：
    goodinfo (預設)  — 爬取 Goodinfo.tw（無需帳號，較慢，約 8 分鐘）
    finmind          — 使用 FinMind API（穩定快速，約 3-5 分鐘）
                       申請免費 token：https://finmindtrade.com/
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
from data_sources_finmind import (
    fetch_company_info_finmind,
    fetch_delisted_codes_finmind,
    build_all_dividend_history_finmind,
    test_finmind_connection,
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


def build(
    top_n: int = 300,
    source: str = "goodinfo",
    token: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """主建置流程。

    Parameters
    ----------
    top_n : int
        取前 N 名市值股票。
    source : str
        股利資料來源：'goodinfo'（預設）或 'finmind'。
    token : str, optional
        FinMind API token（僅 source='finmind' 時使用）。

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

    # --- Step 2: 取得股利歷史 ---
    if source == "finmind":
        logger.info("=== 步驟 2/4：FinMind — 公司資訊 + 下市過濾 + 股利資料 ===")
        if token:
            logger.info("已提供 FinMind token，速率限制：600次/小時")
        else:
            logger.info("未提供 token，速率限制：300次/小時（可至 https://finmindtrade.com/ 免費申請）")

        # 先測試連線
        if not test_finmind_connection(token=token):
            logger.error("FinMind API 連線失敗，請確認網路與 token 設定")
            return pd.DataFrame(), pd.DataFrame()

        # 2a. TaiwanStockInfo：補強產業別（1 次 API 呼叫取代 TWSE/TPEX 公司資訊 + yfinance）
        logger.info("  2a. TaiwanStockInfo 取得產業別…")
        fm_info = fetch_company_info_finmind(
            codes=universe["code"].tolist(),
            token=token,
        )
        if not fm_info.empty:
            # 以 FinMind 的 sector 覆蓋（只補空值，不強制覆蓋已有值）
            universe = universe.merge(fm_info[["code", "sector"]], on="code", how="left", suffixes=("", "_fm"))
            if "sector_fm" in universe.columns:
                universe["sector"] = universe.apply(
                    lambda r: r["sector_fm"] if (not r["sector"] and r["sector_fm"]) else r["sector"],
                    axis=1,
                )
                universe.drop(columns=["sector_fm"], inplace=True)
            universe["sector"] = universe["sector"].fillna("").astype(str)

        # 2b. TaiwanStockDelisting：過濾已下市股票（1 次 API 呼叫）
        logger.info("  2b. TaiwanStockDelisting 過濾已下市股票…")
        delisted = fetch_delisted_codes_finmind(token=token)
        before_count = len(universe)
        if delisted:
            universe = universe[~universe["code"].isin(delisted)].reset_index(drop=True)
            filtered_count = before_count - len(universe)
            if filtered_count > 0:
                logger.info(f"  過濾掉 {filtered_count} 檔已下市股票，剩 {len(universe)} 檔")

        # 2c. TaiwanStockDividend：非同步批次取得股利歷史
        logger.info("  2c. TaiwanStockDividend 批次取得股利歷史…")
        div_hist = build_all_dividend_history_finmind(
            universe,
            token=token,
            delay=0.3 if token else 0.6,
            log_path=log_path,
        )
    else:
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
            "sector": row.get("sector", ""),
            "business_nature": row.get("business_nature", ""),
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
    parser.add_argument("--top", type=int, default=300,
                        help="取前 N 名市值股票 (預設: 300)")
    parser.add_argument("--source", choices=["goodinfo", "finmind"], default="goodinfo",
                        help="股利資料來源：goodinfo（預設）或 finmind")
    parser.add_argument("--token", type=str, default=None,
                        help="FinMind API token（搭配 --source finmind 使用）")
    args = parser.parse_args()

    build(top_n=args.top, source=args.source, token=args.token)
