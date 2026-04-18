# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — 共用工具函式
====================================
提供數值清洗、年度轉換、百分比格式化等通用功能。
"""

from __future__ import annotations

import math
import re
from typing import Optional


def to_float(x) -> float:
    """安全轉換為 float，處理各種格式（逗號、百分號、中文符號）。"""
    if x is None:
        return float("nan")
    s = str(x).strip().replace(",", "").replace("%", "").replace("％", "")
    if s in {"", "--", "-", "nan", "None", "N/A", "─", "−"}:
        return float("nan")
    try:
        return float(s)
    except Exception:
        return float("nan")


def normalize_code(code: str) -> Optional[str]:
    """提取 4 位數股票代號（過濾非股票代號）。"""
    s = str(code).strip()
    m = re.fullmatch(r"(\d{4})", s)
    return m.group(1) if m else None


def roc_to_ad_year(v) -> Optional[int]:
    """將民國年或西元年轉換為西元年（int）。
    
    支援格式：
    - '114' → 2025
    - '114/01/15' → 2025
    - '2025/01/15' → 2025
    - '2025' → 2025
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None

    # 西元年格式 YYYY/MM/DD 或 YYYY-MM-DD
    m = re.match(r"^(\d{4})[/-]\d{1,2}[/-]\d{1,2}$", s)
    if m:
        return int(m.group(1))

    # 民國年格式 YYY/MM/DD 或 YY/MM/DD
    m = re.match(r"^(\d{2,3})[/-]\d{1,2}[/-]\d{1,2}$", s)
    if m:
        y = int(m.group(1))
        return y + 1911 if y < 1911 else y

    # 純數字
    if s.isdigit():
        y = int(s)
        return y + 1911 if y < 1911 else y

    return None


def pct_text(x: float) -> str:
    """格式化百分比顯示。"""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:.2f}%"
