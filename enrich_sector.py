# -*- coding: utf-8 -*-
"""
enrich_sector.py — 補充 screened_dataset.csv 的產業別與主要業務欄位
=======================================================================
不需重新爬取 Goodinfo，直接從 TWSE/TPEX OpenAPI 及 yfinance 補充
sector 與 business_nature，並寫回 screened_dataset.csv。

用法：
    python enrich_sector.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
SCREENED_FILE = DATA_DIR / "screened_dataset.csv"


def main() -> None:
    if not SCREENED_FILE.exists():
        logger.error("找不到 data/screened_dataset.csv，請先執行 build_dataset.py")
        sys.exit(1)

    screened = pd.read_csv(SCREENED_FILE)
    screened["code"] = screened["code"].astype(str)
    logger.info(f"載入 {len(screened)} 筆股票")

    # 建構 universe DataFrame 供 fetch_company_info 使用
    universe = screened[["code", "market"]].copy()

    from data_sources import fetch_company_info
    logger.info("正在取得產業別與主要業務資料（含 yfinance，約 2–5 分鐘）…")
    company_info = fetch_company_info(universe=universe)

    if company_info.empty:
        logger.error("無法取得公司資訊")
        sys.exit(1)

    company_info["code"] = company_info["code"].astype(str)

    # 移除舊的 sector/business_nature（若存在），再 merge 新的
    for col in ["sector", "business_nature"]:
        if col in screened.columns:
            screened = screened.drop(columns=[col])

    screened = screened.merge(company_info[["code", "sector", "business_nature"]],
                              on="code", how="left")
    screened["sector"] = screened["sector"].fillna("").astype(str)
    screened["business_nature"] = screened["business_nature"].fillna("").astype(str)

    filled_sector = (screened["sector"] != "").sum()
    filled_biz = (screened["business_nature"] != "").sum()
    logger.info(f"sector 填充: {filled_sector}/{len(screened)}")
    logger.info(f"business_nature 填充: {filled_biz}/{len(screened)}")

    screened.to_csv(SCREENED_FILE, index=False, encoding="utf-8-sig")
    logger.info(f"✅ 已更新 {SCREENED_FILE}")


if __name__ == "__main__":
    main()
