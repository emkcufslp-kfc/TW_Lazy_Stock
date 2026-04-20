# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — 資料來源模組
======================================
負責從 TWSE/TPEX OpenAPI 取得股票清單與即時價格，
以及從 Goodinfo.tw 爬取歷年股利資料。

資料來源：
- TWSE OpenAPI: https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
- TWSE OpenAPI: https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL
- TPEX OpenAPI: https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes
- Goodinfo.tw:  https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID={code}

TWSE 端點參考來自 pyang2045/twsemcp 開源專案。
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
import urllib3
from bs4 import BeautifulSoup

# 停用 SSL 警告（TWSE/TPEX 政府 API 有 SSL 憑證問題）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from utils import to_float, normalize_code

# --- 設定 ---
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# TWSE / TPEX OpenAPI 端點（參考自 twsemcp）
TWSE_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_BWIBBU_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TPEX_QUOTES = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"

# 公司基本資料（產業別、主要業務）
TWSE_COMPANY_INFO_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_PERATIO_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
TPEX_COMPANY_INFO_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

# yfinance industry cache file
_YF_CACHE_FILE = Path("data/yf_industry_cache.json")

# 產業代碼 → 繁體中文名稱（TWSE/TPEX 共用，t187ap03_L 的 產業別 為數字代碼）
_INDUSTRY_CODE_MAP: dict[str, str] = {
    "01": "水泥工業",  "1": "水泥工業",
    "02": "食品工業",  "2": "食品工業",
    "03": "塑膠工業",  "3": "塑膠工業",
    "04": "紡織纖維",  "4": "紡織纖維",
    "05": "電機機械",  "5": "電機機械",
    "06": "電器電纜",  "6": "電器電纜",
    "07": "化學工業",  "7": "化學工業",
    "08": "玻璃陶瓷",  "8": "玻璃陶瓷",
    "09": "造紙工業",  "9": "造紙工業",
    "10": "鋼鐵工業",
    "11": "橡膠工業",
    "12": "汽車工業",
    "13": "電子工業",
    "14": "建材營造",
    "15": "航運業",
    "16": "觀光餐旅",
    "17": "金融保險",
    "18": "貿易百貨",
    "19": "油電燃氣業",
    "20": "其他",
    "21": "化學生技醫療",
    "22": "電子通路業",
    "23": "資訊服務業",
    "24": "其他電子業",
    "25": "文化創意業",
    "26": "農業科技業",
    "27": "電子商務",
    "28": "觀光餐旅",
    "29": "電子工業",
    "30": "半導體業",
    "31": "電腦及周邊設備業",
    "32": "光電業",
    "33": "通信網路業",
    "34": "電子零組件業",
    "35": "電子通路業",
    "36": "資訊服務業",
    "37": "其他電子業",
}

# Goodinfo 股利政策頁面
GOODINFO_DIV_URL = "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID={code}"


# ============================================================
#  第一層：股票清單與即時價格
# ============================================================

def fetch_twse_stocks() -> pd.DataFrame:
    """從 TWSE OpenAPI 取得所有上市股票的收盤價。
    
    Returns
    -------
    pd.DataFrame
        欄位: code, name, market, price
    """
    try:
        r = requests.get(TWSE_STOCK_DAY_ALL, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"TWSE STOCK_DAY_ALL 取得失敗: {e}")
        return pd.DataFrame()

    rows = []
    for item in data:
        code = normalize_code(item.get("Code", ""))
        if code is None:
            continue
        price = to_float(item.get("ClosingPrice", ""))
        if math.isnan(price) or price <= 0:
            continue
        name = str(item.get("Name", "")).strip()
        rows.append({
            "code": code,
            "name": name,
            "market": "TWSE",
            "price": price,
        })

    df = pd.DataFrame(rows)
    logger.info(f"TWSE 上市股票: {len(df)} 檔")
    return df


def fetch_tpex_stocks() -> pd.DataFrame:
    """從 TPEX OpenAPI 取得所有上櫃股票的收盤價。
    
    Returns
    -------
    pd.DataFrame
        欄位: code, name, market, price
    """
    try:
        r = requests.get(TPEX_QUOTES, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"TPEX quotes 取得失敗: {e}")
        return pd.DataFrame()

    rows = []
    for item in data:
        code = normalize_code(item.get("SecuritiesCompanyCode", ""))
        if code is None:
            continue
        price = to_float(item.get("Close", ""))
        if math.isnan(price) or price <= 0:
            continue
        name = str(item.get("CompanyName", "")).strip()
        trade_value = to_float(item.get("TransactionAmount", "0"))
        rows.append({
            "code": code,
            "name": name,
            "market": "TPEX",
            "price": price,
            "trade_value": trade_value if not math.isnan(trade_value) else 0.0,
        })

    df = pd.DataFrame(rows)
    logger.info(f"TPEX 上櫃股票: {len(df)} 檔")
    return df


def fetch_twse_market_cap_ranking() -> pd.DataFrame:
    """從 TWSE BWIBBU_ALL 取得市值排名所需的輔助資料。
    
    由於 TWSE OpenAPI 不直接提供市值，
    我們使用 STOCK_DAY_ALL 的成交金額 (TradeValue) 作為市值代理指標，
    大型股通常成交金額最高。
    
    Returns
    -------
    pd.DataFrame
        欄位: code, trade_value（成交金額）
    """
    try:
        r = requests.get(TWSE_STOCK_DAY_ALL, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"TWSE market cap proxy 取得失敗: {e}")
        return pd.DataFrame()

    rows = []
    for item in data:
        code = normalize_code(item.get("Code", ""))
        if code is None:
            continue
        trade_value = to_float(item.get("TradeValue", "0"))
        rows.append({"code": code, "trade_value": trade_value})

    return pd.DataFrame(rows)


def _resolve_sector(raw: str) -> str:
    """將數字代碼轉為繁體中文產業別；若已是中文則直接回傳。"""
    raw = raw.strip()
    if not raw:
        return ""
    # 純數字 → 查對照表
    if raw.isdigit() or (len(raw) == 2 and raw[0] == "0" and raw[1].isdigit()):
        return _INDUSTRY_CODE_MAP.get(raw, raw)
    return raw


def _load_yf_cache() -> dict:
    """Load the yfinance industry cache from disk (code -> {sector, industry})."""
    if _YF_CACHE_FILE.exists():
        import json
        try:
            return json.loads(_YF_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_yf_cache(cache: dict) -> None:
    """Persist the yfinance industry cache to disk."""
    import json
    _YF_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _YF_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_yf_industry(codes: list[str], markets: dict[str, str]) -> dict[str, dict]:
    """Fetch sector/industry from yfinance for codes not yet in cache.

    Parameters
    ----------
    codes : list of stock code strings
    markets : dict mapping code -> "TWSE" or "TPEX"

    Returns
    -------
    dict  code -> {"sector": str, "industry": str}
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — skipping yfinance industry fetch")
        return {}

    cache = _load_yf_cache()
    missing = [c for c in codes if c not in cache]
    logger.info(f"yfinance industry: {len(missing)} 筆待查（快取 {len(cache)} 筆）")

    for code in missing:
        mkt = markets.get(code, "TWSE")
        suffix = ".TW" if mkt == "TWSE" else ".TWO"
        try:
            info = yf.Ticker(f"{code}{suffix}").info
            cache[code] = {
                "sector":   str(info.get("sector",   "") or ""),
                "industry": str(info.get("industry", "") or ""),
            }
        except Exception as e:
            logger.debug(f"[{code}] yfinance info failed: {e}")
            cache[code] = {"sector": "", "industry": ""}
        time.sleep(0.3)

    _save_yf_cache(cache)
    return cache


def fetch_company_info(universe: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """從 TWSE/TPEX OpenAPI 及 yfinance 取得公司產業別與主要業務描述。

    資料來源優先順序：
    1. TWSE t187ap03_L → 產業別代碼 → _INDUSTRY_CODE_MAP（繁中）
    2. TPEX mopsfin_t187ap03_O → SecuritiesIndustryCode → _INDUSTRY_CODE_MAP
    3. yfinance .info → sector / industry（英文，作為 business_nature）

    Parameters
    ----------
    universe : pd.DataFrame, optional
        若提供，用於 yfinance 查詢時的 market 對照。
        需含 'code' 與 'market' 欄。

    Returns
    -------
    pd.DataFrame
        欄位: code, sector（繁體中文產業別）, business_nature（英文 industry）
    """
    rows: list[dict] = []

    # --- Step 1: TWSE — t187ap03_L 含產業別代碼 ---
    try:
        r = requests.get(TWSE_COMPANY_INFO_URL, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        for item in r.json():
            code = normalize_code(str(item.get("公司代號", "")))
            if code is None:
                continue
            sector = _resolve_sector(str(item.get("產業別", "")))
            rows.append({"code": code, "sector": sector, "business_nature": ""})
        logger.info(f"TWSE t187ap03_L 公司資料: {len(rows)} 筆")
    except Exception as e:
        logger.warning(f"TWSE t187ap03_L 取得失敗: {e}")

    twse_count = len(rows)

    # --- Step 2: TPEX — mopsfin_t187ap03_O 含 SecuritiesIndustryCode ---
    try:
        r = requests.get(TPEX_COMPANY_INFO_URL, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        for item in r.json():
            code = normalize_code(str(item.get("SecuritiesCompanyCode", "")))
            if code is None:
                continue
            sector = _resolve_sector(str(item.get("SecuritiesIndustryCode", "")))
            rows.append({"code": code, "sector": sector, "business_nature": ""})
        logger.info(f"TPEX mopsfin_t187ap03_O 公司資料: {len(rows) - twse_count} 筆")
    except Exception as e:
        logger.warning(f"TPEX mopsfin_t187ap03_O 取得失敗: {e}")

    if not rows:
        return pd.DataFrame(columns=["code", "sector", "business_nature"])

    df = pd.DataFrame(rows).drop_duplicates("code", keep="first")

    # --- Step 3: yfinance industry → business_nature ---
    if universe is not None and not universe.empty:
        markets = {str(r["code"]): r["market"] for _, r in universe.iterrows()}
    else:
        markets = {r["code"]: "TWSE" for _, r in df.iterrows()}

    yf_data = fetch_yf_industry(df["code"].tolist(), markets)
    if yf_data:
        df["business_nature"] = df["code"].map(
            lambda c: yf_data.get(c, {}).get("industry", "")
        )
        # Fill sector from yfinance where TWSE/TPEX code mapping is empty
        def _fill_sector(row):
            if row["sector"]:
                return row["sector"]
            return yf_data.get(row["code"], {}).get("sector", "")
        df["sector"] = df.apply(_fill_sector, axis=1)

    return df


def fetch_full_universe(top_n: int = 300) -> pd.DataFrame:
    """取得完整股票清單（TWSE + TPEX），各自依成交金額排名後合併取前 N 名。

    Parameters
    ----------
    top_n : int
        TWSE + TPEX 合計保留股票數。
        TWSE 取 top_n * 0.75，TPEX 取 top_n * 0.25（各市場獨立排名）。

    Returns
    -------
    pd.DataFrame
        欄位: code, name, market, price, sector, business_nature
    """
    twse_raw = fetch_twse_stocks()
    tpex_raw = fetch_tpex_stocks()

    if twse_raw.empty and tpex_raw.empty:
        logger.error("無法取得任何股票資料")
        return pd.DataFrame()

    # --- TWSE：用 STOCK_DAY_ALL TradeValue 排序 ---
    twse_n = max(1, int(top_n * 0.75))
    cap_proxy = fetch_twse_market_cap_ranking()
    if not cap_proxy.empty and not twse_raw.empty:
        twse_ranked = twse_raw.merge(cap_proxy, on="code", how="left")
        twse_ranked["trade_value"] = twse_ranked["trade_value"].fillna(0)
        twse_ranked = twse_ranked.sort_values("trade_value", ascending=False).head(twse_n)
        twse_ranked = twse_ranked.drop(columns=["trade_value"])
    else:
        twse_ranked = twse_raw.head(twse_n)

    # --- TPEX：用 TransactionAmount 排序（fetch_tpex_stocks 已包含 trade_value）---
    tpex_n = top_n - len(twse_ranked)
    if not tpex_raw.empty:
        if "trade_value" in tpex_raw.columns:
            tpex_ranked = tpex_raw.sort_values("trade_value", ascending=False).head(tpex_n)
            tpex_ranked = tpex_ranked.drop(columns=["trade_value"])
        else:
            tpex_ranked = tpex_raw.head(tpex_n)
    else:
        tpex_ranked = pd.DataFrame()

    universe = pd.concat([twse_ranked, tpex_ranked], ignore_index=True)
    logger.info(f"篩選後股票清單: TWSE {len(twse_ranked)} + TPEX {len(tpex_ranked)} = {len(universe)} 檔")

    # 合併產業別與主要業務
    company_info = fetch_company_info(universe=universe)
    if not company_info.empty:
        universe = universe.merge(company_info, on="code", how="left")
        universe["sector"] = universe["sector"].fillna("").astype(str)
        universe["business_nature"] = universe["business_nature"].fillna("").astype(str)
    else:
        universe["sector"] = ""
        universe["business_nature"] = ""

    logger.info(f"篩選後股票清單: {len(universe)} 檔")
    return universe


# ============================================================
#  第二層：Goodinfo.tw 股利歷史資料
# ============================================================

# Goodinfo 需要透過 Session + Cookie 模擬才能取得完整頁面
_goodinfo_session: Optional[requests.Session] = None


def _get_goodinfo_session() -> requests.Session:
    """建立或重用一個已設定 CLIENT_KEY cookie 的 Goodinfo Session。
    
    Goodinfo.tw 有 JavaScript 反爬蟲機制：
    第一次請求會回傳一段 JS 設定 CLIENT_KEY cookie 並重新導向。
    我們模擬此 JS 邏輯，手動算出 cookie 值並設定到 Session。
    """
    global _goodinfo_session
    if _goodinfo_session is not None:
        return _goodinfo_session

    session = requests.Session()
    session.headers.update({
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://goodinfo.tw/tw/index.asp",
    })

    # Step 1: 發送初始請求，取得 JS 中的伺服器參數
    try:
        r1 = session.get(
            "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID=2330",
            verify=False, timeout=15,
        )
        r1.encoding = "utf-8"

        # 解析 JS: setCookie('CLIENT_KEY', 'v1|v2|v3|' + ...)
        match = re.search(r"'(\d+\.\d+)\|(\d+\.\d+)\|(\d+\.\d+)\|'", r1.text)
        if match:
            v1, v2, v3 = match.group(1), match.group(2), match.group(3)
            # 模擬 JavaScript: GetTimezoneOffset() = -480 (台灣 UTC+8)
            tz_offset = -480
            # Date.now()/86400000 - GetTimezoneOffset()/1440
            adjusted = time.time() * 1000 / 86400000 - tz_offset / 1440
            client_key = f"{v1}|{v2}|{v3}|{tz_offset}|{adjusted}|{adjusted}"
            session.cookies.set("CLIENT_KEY", client_key, domain="goodinfo.tw", path="/")
            logger.info("Goodinfo SESSION 已建立 (CLIENT_KEY cookie 已設定)")
        else:
            logger.warning("Goodinfo 無法解析 CLIENT_KEY 參數，將嘗試直接存取")

    except Exception as e:
        logger.warning(f"Goodinfo Session 建立失敗: {e}")

    _goodinfo_session = session
    return session


def _find_dividend_dataframe(dfs: list[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """從 pd.read_html 回傳的多個 DataFrame 中，找到股利明細表。
    
    辨識方式：尋找包含 '股利合計' 或 '股利 合計' 欄位名稱的表格，
    且該表格行數 > 5（排除摘要表）。
    """
    for df in dfs:
        if len(df) < 4:
            continue
        # 檢查所有層級的欄位名稱
        col_text = " ".join(str(c) for c in df.columns.tolist())
        if "股利" in col_text and ("合計" in col_text or "盈餘" in col_text):
            return df
    return None


def _parse_goodinfo_dividend_table(html_text: str, code: str) -> pd.DataFrame:
    """解析 Goodinfo.tw 股利政策頁面的股利明細表。
    
    Goodinfo 表格結構（4 級 MultiIndex）：
    - Col 0: 股利發放期間（年度年份或 ∟ 開頭的季度細項）
    - Col 4: 現金股利合計
    - Col 7: 股票股利合計
    - Col 8: 股利合計
    
    我們只取**年度彙總列**（Col 0 為 4 位數西元年），
    忽略 ∟ 開頭的季度明細列。
    
    Returns
    -------
    pd.DataFrame
        欄位: year, cash_div, stock_div, total_div
    """
    from io import StringIO

    try:
        dfs = pd.read_html(StringIO(html_text))
        if not dfs:
            logger.warning(f"[{code}] pd.read_html 找不到任何表格")
            return pd.DataFrame()
    except Exception as e:
        logger.warning(f"[{code}] pd.read_html 解析失敗: {e}")
        return pd.DataFrame()

    # 找到股利明細表
    raw = _find_dividend_dataframe(dfs)
    if raw is None:
        logger.warning(f"[{code}] 找不到股利明細 DataFrame")
        return pd.DataFrame()

    # --- 定位欄位索引 ---
    # 策略：掃描 MultiIndex 各層級尋找關鍵字
    cash_col_idx = None
    stock_col_idx = None
    total_col_idx = None

    if isinstance(raw.columns, pd.MultiIndex):
        for i in range(len(raw.columns)):
            col_parts = [str(raw.columns.get_level_values(lv)[i]).replace("\xa0", " ")
                         for lv in range(raw.columns.nlevels)]
            combined = " ".join(col_parts)

            if "現金股利" in combined and "合計" in combined:
                cash_col_idx = i
            elif "股票股利" in combined and "合計" in combined:
                stock_col_idx = i
            elif "股利" in combined and "合計" in combined and "現金" not in combined and "股票" not in combined:
                total_col_idx = i
    else:
        for i, col_name in enumerate(raw.columns):
            cn = str(col_name).replace("\xa0", " ").strip()
            if "現金股利" in cn and "合計" in cn:
                cash_col_idx = i
            elif "股票股利" in cn and "合計" in cn:
                stock_col_idx = i
            elif "股利合計" in cn or "股利 合計" in cn:
                total_col_idx = i

    # --- 逐列提取年度彙總資料 ---
    rows = []
    for row_idx in range(len(raw)):
        values = raw.iloc[row_idx].tolist()

        # Col 0 = 股利發放期間，必須是 4 位數西元年（如 2025, 2024）
        year_str = str(values[0]).strip()
        if not re.match(r"^\d{4}$", year_str):
            continue

        year_int = int(year_str)
        if year_int < 2000 or year_int > 2100:
            continue

        # 提取各項股利值
        cash = 0.0
        stock = 0.0
        total = 0.0

        if cash_col_idx is not None and cash_col_idx < len(values):
            cash = to_float(values[cash_col_idx])
            if math.isnan(cash):
                cash = 0.0
        if stock_col_idx is not None and stock_col_idx < len(values):
            stock = to_float(values[stock_col_idx])
            if math.isnan(stock):
                stock = 0.0
        if total_col_idx is not None and total_col_idx < len(values):
            total = to_float(values[total_col_idx])
            if math.isnan(total):
                total = 0.0

        # 一致性修正
        if total > 0 and cash == 0 and stock == 0:
            cash = total
        if cash > 0 or stock > 0:
            total = cash + stock

        rows.append({
            "year": year_int,
            "cash_div": round(cash, 4),
            "stock_div": round(stock, 4),
            "total_div": round(total, 4),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_dividend_from_goodinfo(
    code: str,
    max_retries: int = 3,
) -> pd.DataFrame:
    """從 Goodinfo.tw 爬取單一股票的歷年股利資料。
    
    使用 Session + CLIENT_KEY cookie 繞過 Goodinfo 的 JS 反爬蟲機制。
    
    Parameters
    ----------
    code : str
        股票代號（4 位數）。
    max_retries : int
        失敗時最多重試次數。
    
    Returns
    -------
    pd.DataFrame
        欄位: year, cash_div, stock_div, total_div
    """
    session = _get_goodinfo_session()
    url = GOODINFO_DIV_URL.format(code=code)

    for attempt in range(max_retries):
        try:
            r = session.get(url, verify=False, timeout=15)
            r.encoding = "utf-8"

            if r.status_code == 403:
                logger.warning(f"[{code}] Goodinfo 403 被阻擋 (attempt {attempt+1})")
                time.sleep(3 * (attempt + 1))
                continue

            if r.status_code != 200:
                logger.warning(f"[{code}] Goodinfo HTTP {r.status_code}")
                time.sleep(2 * (attempt + 1))
                continue

            # 內容太短代表被阻擋（anti-bot redirect）
            if len(r.text) < 5000:
                logger.warning(f"[{code}] Goodinfo 回傳內容過短 ({len(r.text)} bytes), 可能被阻擋")
                # 重建 Session
                global _goodinfo_session
                _goodinfo_session = None
                session = _get_goodinfo_session()
                time.sleep(3 * (attempt + 1))
                continue

            df = _parse_goodinfo_dividend_table(r.text, code)
            if not df.empty:
                return df

            logger.warning(f"[{code}] Goodinfo 解析結果為空 (attempt {attempt+1})")
            time.sleep(2 * (attempt + 1))

        except requests.exceptions.Timeout:
            logger.warning(f"[{code}] Goodinfo 超時 (attempt {attempt+1})")
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            logger.warning(f"[{code}] Goodinfo 例外: {e} (attempt {attempt+1})")
            time.sleep(2 * (attempt + 1))

    logger.error(f"[{code}] Goodinfo 全部重試失敗")
    return pd.DataFrame()


def build_all_dividend_history(
    universe: pd.DataFrame,
    delay: float = 1.5,
    log_path: Optional[Path] = None,
) -> pd.DataFrame:
    """批次爬取所有股票的股利歷史。
    
    Parameters
    ----------
    universe : pd.DataFrame
        必須包含 'code', 'name', 'market' 欄位。
    delay : float
        每次請求間的延遲秒數（避免 Goodinfo 封鎖）。
    log_path : Path, optional
        建置日誌輸出路徑。
    
    Returns
    -------
    pd.DataFrame
        完整股利歷史，欄位: code, name, market, year, cash_div, stock_div, total_div
    """
    try:
        from tqdm import tqdm
        iterator = tqdm(universe.iterrows(), total=len(universe), desc="爬取股利資料")
    except ImportError:
        iterator = universe.iterrows()

    all_rows = []
    errors = []

    for _, row in iterator:
        code = row["code"]
        name = row["name"]
        market = row["market"]

        div_df = fetch_dividend_from_goodinfo(code)

        if div_df.empty:
            errors.append(f"[{code}] {name} — 無股利資料")
        else:
            div_df["code"] = code
            div_df["name"] = name
            div_df["market"] = market
            all_rows.append(div_df)

        time.sleep(delay)

    # 寫入日誌
    if log_path and errors:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"建置時間: {datetime.now().isoformat()}\n")
            f.write(f"總股票數: {len(universe)}\n")
            f.write(f"成功: {len(universe) - len(errors)}\n")
            f.write(f"失敗: {len(errors)}\n\n")
            for e in errors:
                f.write(e + "\n")

    if not all_rows:
        return pd.DataFrame()

    result = pd.concat(all_rows, ignore_index=True)
    # 重新排列欄位順序
    result = result[["code", "name", "market", "year", "cash_div", "stock_div", "total_div"]]
    return result


def ensure_data_dir() -> Path:
    """確保 data/ 目錄存在。"""
    path = Path("data")
    path.mkdir(parents=True, exist_ok=True)
    return path
