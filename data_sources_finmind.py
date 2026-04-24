# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — FinMind 資料來源模組
=============================================
使用 FinMind API (v4) 取代以下資料來源：
  - Goodinfo.tw 爬蟲       → TaiwanStockDividend（股利歷史）
  - TWSE t187ap03_L        → TaiwanStockInfo（公司/產業資訊）
  - TPEX mopsfin_t187ap03_O → TaiwanStockInfo（同上）
  - yfinance                → TaiwanStockInfo（同上）
  - 新增：TaiwanStockDelisting（下市過濾）

殖利率計算公式與篩選規則完全不變，僅改善資料取得效率。

API v4 端點：https://api.finmindtrade.com/api/v4/data
認證方式：Authorization: Bearer {token}
速率限制：600 次/小時（有 token）｜300 次/小時（無 token）
免費申請 token：https://finmindtrade.com/
"""

from __future__ import annotations

import logging
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from utils import to_float, normalize_code

logger = logging.getLogger(__name__)

FINMIND_API_URL  = "https://api.finmindtrade.com/api/v4/data"
DEFAULT_START_DATE = "2015-01-01"   # 涵蓋近 10 年股利歷史
REQUEST_TIMEOUT    = 20             # 秒


# ============================================================
#  核心 HTTP 工具
# ============================================================

def _finmind_get(
    dataset: str,
    data_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    token: Optional[str] = None,
    max_retries: int = 3,
) -> Optional[list[dict]]:
    """
    向 FinMind v4 API 發出 GET 請求。

    認證：使用 Authorization: Bearer {token} header（非 query param）。
    資料識別：使用 data_id 參數（非 stock_id）。

    Returns
    -------
    list[dict] | None
        成功時回傳 data 列表；失敗或超過速率限制時回傳 None。
    """
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params: dict[str, str] = {"dataset": dataset}
    if data_id:
        params["data_id"] = data_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    for attempt in range(max_retries):
        try:
            r = requests.get(
                FINMIND_API_URL,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            payload = r.json()

            status = payload.get("status")

            if status == 200:
                return payload.get("data", [])

            if status == 402:
                # 超過速率限制，不重試
                logger.error(
                    "FinMind API 用量超出上限（HTTP 402）。"
                    "請稍後再試，或升級方案：https://finmindtrade.com/"
                )
                return None

            msg = payload.get("msg", "unknown")
            logger.warning(
                f"[{dataset}/{data_id}] FinMind status={status} msg={msg} "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(2 * (attempt + 1))

        except requests.exceptions.Timeout:
            logger.warning(
                f"[{dataset}/{data_id}] FinMind 逾時 (attempt {attempt + 1})"
            )
            time.sleep(3 * (attempt + 1))
        except Exception as exc:
            logger.warning(
                f"[{dataset}/{data_id}] FinMind 例外: {exc} (attempt {attempt + 1})"
            )
            time.sleep(2 * (attempt + 1))

    logger.error(f"[{dataset}/{data_id}] FinMind 全部重試失敗")
    return None


# ============================================================
#  1. 公司基本資料：TaiwanStockInfo
#     取代：TWSE t187ap03_L + TPEX mopsfin_t187ap03_O + yfinance
# ============================================================

# TaiwanStockInfo.type → 我們的 market 欄位
_TYPE_TO_MARKET: dict[str, str] = {
    "twse":  "TWSE",
    "tpex":  "TPEX",
    "TWSE":  "TWSE",
    "TPEX":  "TPEX",
}


def fetch_company_info_finmind(
    codes: Optional[list[str]] = None,
    token: Optional[str] = None,
) -> pd.DataFrame:
    """
    使用 TaiwanStockInfo 取得公司產業別與市場別。

    一次 API 呼叫取代原本的 4 個來源（TWSE/TPEX 公司資料 + yfinance），
    且 industry_category 直接是繁體中文，不需代碼對照。

    Parameters
    ----------
    codes : list[str], optional
        若提供，僅保留這些股票代號的資料（用於 merge 過濾）。
        不影響 API 呼叫數（TaiwanStockInfo 無法按 data_id 篩選）。
    token : str, optional
        FinMind API token。

    Returns
    -------
    pd.DataFrame
        欄位: code (str), sector (str), market_fm (str)
        market_fm = "TWSE" 或 "TPEX"（可用於補充/覆蓋 TWSE/TPEX API 的 market 欄）
    """
    raw = _finmind_get("TaiwanStockInfo", token=token)
    if raw is None:
        logger.warning("TaiwanStockInfo 取得失敗，公司資訊將為空")
        return pd.DataFrame(columns=["code", "sector", "market_fm"])

    rows: list[dict] = []
    for item in raw:
        code = normalize_code(str(item.get("stock_id", "")))
        if code is None:
            continue

        raw_type   = str(item.get("type", "")).lower().strip()
        market_fm  = _TYPE_TO_MARKET.get(raw_type, "")
        sector     = str(item.get("industry_category", "")).strip()

        rows.append({
            "code":       code,
            "sector":     sector,
            "market_fm":  market_fm,
        })

    if not rows:
        return pd.DataFrame(columns=["code", "sector", "market_fm"])

    df = pd.DataFrame(rows).drop_duplicates("code", keep="first")

    if codes is not None:
        code_set = set(codes)
        df = df[df["code"].isin(code_set)].reset_index(drop=True)

    logger.info(
        f"TaiwanStockInfo: {len(df)} 筆公司資料（TWSE "
        f"{(df['market_fm']=='TWSE').sum()} / "
        f"TPEX {(df['market_fm']=='TPEX').sum()}）"
    )
    return df


# ============================================================
#  2. 下市股票過濾：TaiwanStockDelisting
# ============================================================

def fetch_delisted_codes_finmind(
    token: Optional[str] = None,
) -> set[str]:
    """
    使用 TaiwanStockDelisting 取得已下市股票代號集合。

    用於在股利歷史批次查詢前，過濾掉已下市股票，避免浪費 API 配額。

    Returns
    -------
    set[str]
        已下市股票代號集合（4 位數字串）。
    """
    raw = _finmind_get("TaiwanStockDelisting", token=token)
    if raw is None:
        logger.warning("TaiwanStockDelisting 取得失敗，跳過下市過濾")
        return set()

    delisted: set[str] = set()
    for item in raw:
        code = normalize_code(str(item.get("stock_id", "")))
        if code:
            delisted.add(code)

    logger.info(f"TaiwanStockDelisting: {len(delisted)} 檔已下市股票")
    return delisted


# ============================================================
#  3. 股利歷史：TaiwanStockDividend
# ============================================================

def _parse_dividend_rows(raw_data: list[dict]) -> dict[str, list[dict]]:
    """
    將 FinMind TaiwanStockDividend 原始資料解析並按股票代號分組。

    欄位對應：
      cash_div  = CashEarningsDistribution + CashStatutorySurplus
      stock_div = StockEarningsDistribution + StockStatutorySurplus
      total_div = cash_div + stock_div

    year 取自 FinMind 的 year 欄（股利所屬年度）；
    若 year 欄不可用則 fallback 至 date 欄的年份。

    Returns
    -------
    dict[str, list[dict]]
        { stock_id: [{"year": int, "cash_div": float, "stock_div": float, "total_div": float}, ...] }
    """
    grouped: dict[str, list[dict]] = {}

    for item in raw_data:
        # 股票代號
        code = normalize_code(str(item.get("stock_id", "")))
        if code is None:
            continue

        # 年度解析
        year_raw = str(item.get("year", "")).strip()
        m = re.match(r"(\d{4})", year_raw)
        if m:
            year_int = int(m.group(1))
        else:
            date_raw = str(item.get("date", "")).strip()
            m2 = re.match(r"(\d{4})", date_raw)
            if not m2:
                continue
            year_int = int(m2.group(1))

        if not (2000 <= year_int <= 2100):
            continue

        # 現金股利
        ce = to_float(item.get("CashEarningsDistribution", 0))
        cs = to_float(item.get("CashStatutorySurplus", 0))
        cash_div = (0.0 if math.isnan(ce) else ce) + (0.0 if math.isnan(cs) else cs)

        # 股票股利
        se = to_float(item.get("StockEarningsDistribution", 0))
        ss = to_float(item.get("StockStatutorySurplus", 0))
        stock_div = (0.0 if math.isnan(se) else se) + (0.0 if math.isnan(ss) else ss)

        total_div = cash_div + stock_div

        grouped.setdefault(code, []).append({
            "year":      year_int,
            "cash_div":  cash_div,
            "stock_div": stock_div,
            "total_div": total_div,
        })

    return grouped


def _aggregate_dividend_by_year(rows: list[dict]) -> pd.DataFrame:
    """將同一股票的多筆原始記錄按年度加總（處理季配息）。"""
    if not rows:
        return pd.DataFrame()
    df = (
        pd.DataFrame(rows)
        .groupby("year", as_index=False)[["cash_div", "stock_div", "total_div"]]
        .sum()
        .sort_values("year")
        .reset_index(drop=True)
    )
    df[["cash_div", "stock_div", "total_div"]] = df[
        ["cash_div", "stock_div", "total_div"]
    ].round(4)
    return df


def fetch_dividend_from_finmind(
    code: str,
    start_date: str = DEFAULT_START_DATE,
    token: Optional[str] = None,
) -> pd.DataFrame:
    """
    從 FinMind API 取得單一股票的歷年股利資料（序列模式用）。

    Returns
    -------
    pd.DataFrame
        欄位: year (int), cash_div (float), stock_div (float), total_div (float)
        已按 year 彙整。
    """
    raw = _finmind_get(
        "TaiwanStockDividend",
        data_id=code,
        start_date=start_date,
        token=token,
    )
    if raw is None or not raw:
        return pd.DataFrame()

    grouped = _parse_dividend_rows(raw)
    rows = grouped.get(code, [])
    return _aggregate_dividend_by_year(rows)


# ============================================================
#  4. 批次股利歷史：SDK 非同步（優先）+ 序列 fallback
# ============================================================

def _try_sdk_async_batch(
    codes: list[str],
    start_date: str,
    token: Optional[str],
) -> Optional[pd.DataFrame]:
    """
    嘗試使用 FinMind Python SDK 的非同步批次模式一次取得所有股票的股利。

    SDK async 會同時發出所有請求，大幅縮短總耗時：
      - 序列模式（300 檔 × 0.6 秒延遲）≈ 3–5 分鐘
      - SDK async（300 檔同時發出）        ≈ 10–30 秒

    Returns
    -------
    pd.DataFrame | None
        成功時回傳合併的原始 DataFrame；失敗時回傳 None（由 caller 改用序列）。
    """
    try:
        from FinMind.data import DataLoader  # type: ignore
    except ImportError:
        logger.info("FinMind SDK 未安裝（pip install finmind），改用序列模式")
        return None

    try:
        api = DataLoader()
        if token:
            api.login_by_token(api_token=token)

        logger.info(
            f"[FinMind SDK] 非同步批次查詢 {len(codes)} 檔股票股利資料…"
        )
        df = api.taiwan_stock_dividend(
            stock_id_list=codes,
            start_date=start_date,
            use_async=True,
        )
        if df is None or (hasattr(df, "empty") and df.empty):
            logger.warning("[FinMind SDK] async 回傳空結果，改用序列模式")
            return None

        logger.info(f"[FinMind SDK] async 取得 {len(df)} 筆原始記錄")
        return df

    except Exception as exc:
        logger.warning(f"[FinMind SDK] async 批次失敗: {exc}，改用序列模式")
        return None


def build_all_dividend_history_finmind(
    universe: pd.DataFrame,
    token: Optional[str] = None,
    start_date: str = DEFAULT_START_DATE,
    delay: float = 0.6,
    log_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    批次取得所有股票的歷年股利資料。

    執行策略（自動選擇）：
    1. 優先：FinMind Python SDK + use_async=True
       → 全部股票同時發出請求，約 10–30 秒完成
    2. Fallback：逐一 requests.get 序列模式
       → 每檔間隔 delay 秒，避免超過速率限制

    篩選規則（screening.py）與殖利率公式完全不變，
    此函式只負責取得 (code, year, cash_div, stock_div, total_div) 資料。

    Parameters
    ----------
    universe : pd.DataFrame
        必須包含 'code', 'name', 'market' 欄位。
    token : str, optional
        FinMind API token（有 token 時 delay 可縮短至 0.3 秒）。
    start_date : str
        資料起始日期。
    delay : float
        序列模式每次請求間延遲（秒）。
    log_path : Path, optional
        建置日誌輸出路徑。

    Returns
    -------
    pd.DataFrame
        欄位: code, name, market, year, cash_div, stock_div, total_div
    """
    codes     = universe["code"].tolist()
    meta      = universe.set_index("code")[["name", "market"]].to_dict("index")
    all_rows: list[pd.DataFrame] = []
    errors:   list[str]          = []

    # ── 路徑 1：SDK async batch ───────────────────────────────
    sdk_df = _try_sdk_async_batch(codes, start_date, token)

    if sdk_df is not None:
        # SDK 回傳的 DataFrame 含 stock_id 欄
        raw_records = sdk_df.to_dict("records")
        grouped = _parse_dividend_rows(raw_records)

        for code in codes:
            rows = grouped.get(code, [])
            agg  = _aggregate_dividend_by_year(rows)
            info = meta.get(code, {"name": code, "market": ""})

            if agg.empty:
                errors.append(f"[{code}] {info['name']} — 無股利資料")
            else:
                agg["code"]   = code
                agg["name"]   = info["name"]
                agg["market"] = info["market"]
                all_rows.append(agg)

    else:
        # ── 路徑 2：序列 requests ─────────────────────────────
        logger.info(
            f"[FinMind] 序列模式：{len(codes)} 檔，"
            f"間隔 {delay}s，預估 {len(codes) * delay / 60:.1f} 分鐘"
        )
        try:
            from tqdm import tqdm
            iterator = tqdm(codes, desc="[FinMind] 股利資料")
        except ImportError:
            iterator = codes  # type: ignore

        for code in iterator:
            agg  = fetch_dividend_from_finmind(code, start_date=start_date, token=token)
            info = meta.get(code, {"name": code, "market": ""})

            if agg.empty:
                errors.append(f"[{code}] {info['name']} — 無股利資料")
            else:
                agg["code"]   = code
                agg["name"]   = info["name"]
                agg["market"] = info["market"]
                all_rows.append(agg)

            time.sleep(delay)

    # ── 寫入日誌 ─────────────────────────────────────────────
    if log_path:
        mode = "a" if log_path.exists() else "w"
        with open(log_path, mode, encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"[FinMind] 股利建置時間: {datetime.now().isoformat()}\n")
            f.write(f"總股票數: {len(codes)}\n")
            f.write(f"成功: {len(codes) - len(errors)}\n")
            f.write(f"失敗: {len(errors)}\n")
            if errors:
                f.write("\n失敗清單:\n")
                for e in errors:
                    f.write(e + "\n")

    if not all_rows:
        return pd.DataFrame()

    result = pd.concat(all_rows, ignore_index=True)
    result = result[["code", "name", "market", "year", "cash_div", "stock_div", "total_div"]]
    logger.info(
        f"[FinMind] 股利資料完成：{len(result)} 筆 / "
        f"{len(errors)} 檔無資料"
    )
    return result


# ============================================================
#  5. 連線測試
# ============================================================

def test_finmind_connection(token: Optional[str] = None) -> bool:
    """
    快速測試 FinMind API 連線是否正常（用台積電 2330 做測試）。

    Returns
    -------
    bool
        True = 連線正常。
    """
    try:
        raw = _finmind_get(
            "TaiwanStockDividend",
            data_id="2330",
            start_date="2023-01-01",
            token=token,
            max_retries=1,
        )
        if raw is None:
            logger.error("FinMind 連線測試失敗（API 回傳 None）")
            return False
        logger.info(f"FinMind 連線測試成功（2330 近期記錄 {len(raw)} 筆）")
        return True
    except Exception as exc:
        logger.error(f"FinMind 連線測試失敗: {exc}")
        return False
