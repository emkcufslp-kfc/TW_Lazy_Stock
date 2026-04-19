# -*- coding: utf-8 -*-
"""
台股股利選股 Dashboard — Streamlit 主程式
==========================================
Premium 互動式股利選股 Dashboard。
使用者可透過滑桿調整殖利率門檻，查看符合條件的股票清單與個股明細。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime, date, timedelta
import os

from data_sources import fetch_company_info

# --- 頁面設定 ---
st.set_page_config(
    page_title="台股股利選股 Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 自訂 CSS （Premium 風格）---
st.markdown("""
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

    * { font-family: 'Noto Sans TC', sans-serif; }

    /* KPI 卡片 */
    .kpi-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%);
        border: 1px solid rgba(0, 212, 170, 0.2);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(0, 212, 170, 0.15);
    }
    .kpi-icon { font-size: 2rem; margin-bottom: 8px; }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #00D4AA;
        margin: 4px 0;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #8892a4;
        letter-spacing: 0.5px;
    }

    /* 規則說明區 */
    .rule-box {
        background: linear-gradient(135deg, #1e2740 0%, #1a2035 100%);
        border-left: 4px solid #00D4AA;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
        font-size: 0.88rem;
        color: #b0b8c8;
    }
    .rule-box strong { color: #e0e0e0; }

    /* 標題裝飾 */
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00D4AA, #00B4D8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .subtitle {
        color: #6b7b8d;
        font-size: 0.95rem;
        margin-bottom: 24px;
    }

    /* 隱藏 Streamlit 預設 footer */
    footer { visibility: hidden; }

    /* 表格標題美化 */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #e0e0e0;
        border-bottom: 2px solid #00D4AA;
        padding-bottom: 8px;
        margin-top: 32px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)


# --- 路徑設定 ---
DATA_DIR = Path("data")
SCREENED_FILE = DATA_DIR / "screened_dataset.csv"
DIV_FILE = DATA_DIR / "dividend_history.csv"


# --- 資料載入 ---
@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """載入預建的 CSV 資料，並即時補充產業別與主要業務欄位。"""
    screened = pd.read_csv(SCREENED_FILE)
    div_hist = pd.read_csv(DIV_FILE)

    # 若 CSV 尚未包含 sector/business_nature，即時從 API 補充
    if "sector" not in screened.columns or "business_nature" not in screened.columns:
        try:
            company_info = fetch_company_info()
            if not company_info.empty:
                screened["code"] = screened["code"].astype(str)
                company_info["code"] = company_info["code"].astype(str)
                screened = screened.merge(company_info, on="code", how="left")
        except Exception:
            pass
        if "sector" not in screened.columns:
            screened["sector"] = ""
        if "business_nature" not in screened.columns:
            screened["business_nature"] = ""
    screened["sector"] = screened["sector"].fillna("").astype(str)
    screened["business_nature"] = screened["business_nature"].fillna("").astype(str)

    return screened, div_hist


def get_data_freshness() -> str:
    """取得資料檔的最後修改時間。"""
    if SCREENED_FILE.exists():
        ts = os.path.getmtime(SCREENED_FILE)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    return "未知"


def render_kpi_card(icon: str, value: str, label: str) -> str:
    """生成 KPI 卡片的 HTML。"""
    return f"""
    <div class="kpi-card">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """


def create_dividend_trend_chart(sub: pd.DataFrame, code: str, name: str) -> go.Figure:
    """建立股利趨勢圖（分組長條圖 + 總額折線）。"""
    fig = go.Figure()

    # 現金股利 (藍色)
    fig.add_trace(go.Bar(
        x=sub["year"],
        y=sub["cash_div"],
        name="現金股利",
        marker_color="#00B4D8",
        opacity=0.85,
    ))

    # 股票股利 (橙色)
    fig.add_trace(go.Bar(
        x=sub["year"],
        y=sub["stock_div"],
        name="股票股利",
        marker_color="#FF8C42",
        opacity=0.85,
    ))

    # 合計折線 (綠色)
    fig.add_trace(go.Scatter(
        x=sub["year"],
        y=sub["total_div"],
        name="股利合計",
        mode="lines+markers",
        line=dict(color="#00D4AA", width=3),
        marker=dict(size=8),
    ))

    fig.update_layout(
        title=dict(
            text=f"{code} {name} — 歷年股利趨勢",
            font=dict(size=16, color="#e0e0e0"),
        ),
        xaxis=dict(
            title="年度", dtick=1,
            gridcolor="rgba(255,255,255,0.05)",
        ),
        yaxis=dict(
            title="股利（元）",
            gridcolor="rgba(255,255,255,0.08)",
        ),
        barmode="stack",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c0c8d4"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
        ),
        margin=dict(l=40, r=20, t=60, b=40),
        height=400,
    )
    return fig


def create_yield_comparison_chart(current_yield: float, avg_5y: float) -> go.Figure:
    """建立殖利率比較圖（水平長條）。"""
    fig = go.Figure()

    categories = ["目前殖利率", "平均 5 年殖利率"]
    values = [current_yield, avg_5y]
    colors = ["#00D4AA", "#00B4D8"]

    fig.add_trace(go.Bar(
        y=categories,
        x=values,
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=0),
        ),
        text=[f"{v:.2f}%" for v in values],
        textposition="auto",
        textfont=dict(size=14, color="white"),
    ))

    fig.update_layout(
        title=dict(
            text="殖利率比較",
            font=dict(size=16, color="#e0e0e0"),
        ),
        xaxis=dict(
            title="殖利率 (%)",
            gridcolor="rgba(255,255,255,0.08)",
        ),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c0c8d4"),
        margin=dict(l=20, r=20, t=50, b=40),
        height=220,
        showlegend=False,
    )
    return fig


# ============================================================
#  主程式
# ============================================================

def main():
    # --- 標題 ---
    st.markdown('<div class="main-title">💰 台股股利選股 Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">基於連續 10 年股利發放紀錄的機構級選股系統</div>', unsafe_allow_html=True)

    # --- 規則說明 ---
    st.markdown("""
    <div class="rule-box">
        <strong>📋 篩選規則：</strong><br>
        ① 最近 10 個曆年（2016–2025），每一年都有發放股利<br>
        ② 目前殖利率 ≥ 使用者設定門檻<br>
        ③ 平均 5 年殖利率 ≥ 使用者設定門檻<br>
        <strong>⚠️ 殖利率定義 = （現金股利 + 股票股利）/ 現價</strong>
    </div>
    """, unsafe_allow_html=True)

    # --- 檢查資料檔 ---
    if not SCREENED_FILE.exists() or not DIV_FILE.exists():
        st.error("⚠️ 找不到資料檔！請先執行 `python build_dataset.py` 建置資料。")
        st.code("python build_dataset.py", language="bash")
        st.stop()

    screened, div_hist = load_data()

    # ========== SIDEBAR ==========
    with st.sidebar:
        st.markdown("### 📊 篩選條件")
        
        # 資料狀態卡片
        freshness = get_data_freshness()
        st.markdown(f"""
        <div style="background-color:rgba(0,212,170,0.1); border-radius:10px; padding:12px; border:1px solid rgba(0,212,170,0.3); margin-bottom:10px;">
            <div style="font-size:0.75rem; color:#8892a4;">資料同步狀態</div>
            <div style="font-weight:600; color:#00D4AA;">✅ 已離線預建完成</div>
            <div style="font-size:0.75rem; color:#6b7b8d; margin-top:4px;">最後更新: {freshness}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 清除快取並重新載入"):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        min_current = st.slider(
            "目前殖利率最低門檻 (%)",
            min_value=0.0, max_value=20.0, value=4.0, step=0.1,
            help="設定目前殖利率的最低門檻"
        )
        min_avg5 = st.slider(
            "平均 5 年殖利率最低門檻 (%)",
            min_value=0.0, max_value=20.0, value=4.0, step=0.1,
            help="設定近 5 年平均殖利率的最低門檻"
        )

        st.divider()

        market = st.radio(
            "🏢 市場",
            ["全部", "上市 (TWSE)", "上櫃 (TPEX)"],
            index=0
        )

        sort_by = st.selectbox(
            "📋 排序方式",
            ["平均 5 年殖利率 ↓", "目前殖利率 ↓", "股票代號 ↑"]
        )

        st.divider()

        # 觀察清單日期 + Screen 按鈕
        today = date.today()
        watchlist_date = st.date_input(
            "📅 觀察清單日期",
            value=st.session_state.get("watchlist_date", today),
            min_value=today.replace(year=today.year - 10),
            max_value=today,
            help="選擇標記此觀察清單的日期，每次更改日期後按 Screen 重新篩選",
            key="watchlist_date_input",
        )
        apply_btn = st.button("📋 Screen", use_container_width=True, type="primary")

        # 顯示上次篩選結果摘要
        meta = st.session_state.get("watchlist_meta")
        if meta:
            prev_date = meta["date"].strftime("%d.%b.%Y")
            prev_n = len(st.session_state.get("watchlist_df", []))
            st.markdown(
                f'<div style="font-size:0.75rem; color:#6b7b8d; padding:4px 2px;">'
                f'上次篩選：{prev_date} · {prev_n} 檔 · '
                f'殖利率 ≥ {meta["min_current"]:.1f}%</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown("""
        <div style="font-size:0.8rem; color:#6b7b8d; padding:8px;">
            💡 <strong>如何更新資料？</strong><br>
            由於 Goodinfo 限制，雲端無法自動抓取。請於本機執行 <code>build_dataset.py</code> 後推送到 GitHub 即可更新。
        </div>
        <div style="font-size:0.8rem; color:#6b7b8d; padding:8px; margin-top:8px;">
            💡 <strong>殖利率定義：</strong><br>
            本系統之殖利率 = 現金股利 + 股票股利<br>
            與市場常見「現金殖利率」不同
        </div>
        """, unsafe_allow_html=True)

    # ========== 篩選邏輯 ==========
    filtered = screened.copy()
    filtered = filtered[
        (filtered["current_yield_pct"] >= min_current) &
        (filtered["avg_5y_yield_pct"] >= min_avg5)
    ]

    if market == "上市 (TWSE)":
        filtered = filtered[filtered["market"] == "TWSE"]
    elif market == "上櫃 (TPEX)":
        filtered = filtered[filtered["market"] == "TPEX"]

    sort_map = {
        "平均 5 年殖利率 ↓": (["avg_5y_yield_pct", "current_yield_pct", "code"], [False, False, True]),
        "目前殖利率 ↓": (["current_yield_pct", "avg_5y_yield_pct", "code"], [False, False, True]),
        "股票代號 ↑": (["code"], [True]),
    }
    sort_cols, sort_asc = sort_map[sort_by]
    filtered = filtered.sort_values(sort_cols, ascending=sort_asc).reset_index(drop=True)

    # ---- 歷史殖利率重算輔助函式 ----
    def _hist_metrics(sub_div: pd.DataFrame, price: float) -> dict | None:
        """Recompute yield metrics from historical dividend data at a given price."""
        yearly = sub_div.groupby("year")["total_div"].sum()
        if yearly.empty or price <= 0:
            return None
        latest_year = int(yearly.index.max())
        latest_div  = float(yearly[latest_year])
        recent_5y   = yearly.sort_index().tail(5)
        sum_5y      = float(recent_5y.sum())
        return {
            "current_yield_pct":    round(latest_div / price * 100, 4),
            "avg_5y_yield_pct":     round(sum_5y / len(recent_5y) / price * 100, 4),
            "latest_paid_year":     latest_year,
            "latest_paid_total_div":round(latest_div, 4),
            "sum_5y_div":           round(sum_5y, 4),
        }

    # 儲存觀察清單到 session state（按下 Screen 時）
    if apply_btn:
        target_date = st.session_state["watchlist_date_input"]
        today_date  = date.today()

        if target_date < today_date:
            # ── 歷史模式：用 yfinance 取得該日股價，重算殖利率再篩選 ──
            with st.spinner(f"正在取得 {target_date.strftime('%Y-%m-%d')} 歷史股價（共 {len(screened)} 檔）…"):
                from technical import get_historical_prices_batch
                stock_list = [
                    {"code": str(r["code"]), "market": r["market"]}
                    for _, r in screened.iterrows()
                ]
                hist_prices = get_historical_prices_batch(stock_list, target_date)

            target_year = target_date.year
            rows = []
            for _, row in screened.iterrows():
                code  = str(row["code"])
                price = hist_prices.get(code)
                if not price or price <= 0:
                    continue
                sub_d = div_hist[div_hist["code"].astype(str) == code]
                sub_d = sub_d[sub_d["year"] < target_year]
                if sub_d.empty:
                    continue
                m = _hist_metrics(sub_d, price)
                if m is None:
                    continue
                rows.append({"code": code, "name": row["name"], "market": row["market"],
                             "price": price,
                             "sector": str(row.get("sector", "")),
                             "business_nature": str(row.get("business_nature", "")),
                             **m})

            if rows:
                hist_df = pd.DataFrame(rows)
                hist_df["code"] = hist_df["code"].astype(str)
                hist_filtered = hist_df[
                    (hist_df["current_yield_pct"] >= min_current) &
                    (hist_df["avg_5y_yield_pct"]  >= min_avg5)
                ]
                if market == "上市 (TWSE)":
                    hist_filtered = hist_filtered[hist_filtered["market"] == "TWSE"]
                elif market == "上櫃 (TPEX)":
                    hist_filtered = hist_filtered[hist_filtered["market"] == "TPEX"]
                sort_cols2, sort_asc2 = sort_map[sort_by]
                hist_filtered = hist_filtered.sort_values(sort_cols2, ascending=sort_asc2).reset_index(drop=True)
                st.session_state["watchlist_df"] = hist_filtered
                st.success(f"歷史篩選完成：{len(hist_prices)} 檔取得股價 → 篩選後 {len(hist_filtered)} 檔")
            else:
                st.warning("無法取得該日期的歷史股價，已改用當前資料。")
                st.session_state["watchlist_df"] = filtered.copy()
        else:
            # ── 今日模式：直接使用預建資料 ──
            st.session_state["watchlist_df"] = filtered.copy()

        st.session_state["watchlist_meta"] = {
            "min_current": min_current,
            "min_avg5":    min_avg5,
            "market":      market,
            "date":        target_date,
        }
        st.session_state["wvf_results"] = None  # 清除舊掃描結果

    # ========== KPI 卡片 ==========
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(render_kpi_card(
            "📊", str(len(filtered)), "符合條件股票數"
        ), unsafe_allow_html=True)

    with c2:
        avg_curr = f"{filtered['current_yield_pct'].mean():.2f}%" if not filtered.empty else "-"
        st.markdown(render_kpi_card(
            "💹", avg_curr, "平均目前殖利率"
        ), unsafe_allow_html=True)

    with c3:
        avg_5y = f"{filtered['avg_5y_yield_pct'].mean():.2f}%" if not filtered.empty else "-"
        st.markdown(render_kpi_card(
            "📈", avg_5y, "平均 5 年殖利率"
        ), unsafe_allow_html=True)

    st.markdown("", unsafe_allow_html=True)  # 間距

    # ========== 股票清單 ==========
    st.markdown('<div class="section-header">📋 篩選結果股票清單</div>', unsafe_allow_html=True)

    if filtered.empty:
        st.info("🔍 目前沒有符合條件的股票，請嘗試調低殖利率門檻。")
    else:
        # 表格欄位設定
        base_cols = [
            "code", "name", "sector", "business_nature", "price",
            "latest_paid_year", "latest_paid_total_div",
            "current_yield_pct", "sum_5y_div", "avg_5y_yield_pct",
        ]
        # 相容舊 CSV（若尚未重建資料，sector/business_nature 欄可能不存在）
        display_cols = [c for c in base_cols if c in filtered.columns]
        display_df = filtered[display_cols].copy()
        col_name_map = {
            "code": "代號", "name": "名稱",
            "sector": "產業別", "business_nature": "主要業務",
            "price": "現價",
            "latest_paid_year": "最新配年", "latest_paid_total_div": "最新總股利",
            "current_yield_pct": "目前殖利率%", "sum_5y_div": "近5年總股利",
            "avg_5y_yield_pct": "平均5年殖利率%",
        }
        display_df.columns = [col_name_map[c] for c in display_cols]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "代號": st.column_config.TextColumn(width="small"),
                "名稱": st.column_config.TextColumn(width="small"),
                "產業別": st.column_config.TextColumn(width="medium"),
                "主要業務": st.column_config.TextColumn(width="large"),
                "現價": st.column_config.NumberColumn(format="%.2f", width="small"),
                "最新配年": st.column_config.NumberColumn(format="%d", width="small"),
                "最新總股利": st.column_config.NumberColumn(format="%.2f", width="small"),
                "目前殖利率%": st.column_config.NumberColumn(format="%.2f", width="small"),
                "近5年總股利": st.column_config.NumberColumn(format="%.2f", width="small"),
                "平均5年殖利率%": st.column_config.NumberColumn(format="%.2f", width="small"),
            },
            height=min(400, 40 + len(display_df) * 35),
        )

        # ── 觀察清單儲存區 ──────────────────────────────────────────
        wl = st.session_state.get("watchlist_df")
        meta = st.session_state.get("watchlist_meta")

        if wl is not None and meta is not None:
            d = meta["date"]
            date_str = d.strftime("%d.%b.%Y")          # e.g. 20.Apr.2026
            c_pct = meta["min_current"]
            a_pct = meta["min_avg5"]
            # xx: 若兩個門檻相同就用一個數字，否則 c{x}-a{y}
            if c_pct == a_pct:
                xx = f"{c_pct:.1f}".rstrip("0").rstrip(".")
            else:
                xx = f"c{c_pct:.1f}-a{a_pct:.1f}".rstrip("0")
            filename = f"TW_Div_{xx}_{date_str}.csv"

            watchlist_cols = [
                c for c in ["code", "name", "sector", "market", "price",
                             "current_yield_pct", "avg_5y_yield_pct",
                             "latest_paid_year", "latest_paid_total_div",
                             "business_nature"]
                if c in wl.columns
            ]
            wl_export = wl[watchlist_cols].copy()
            wl_export.columns = [
                {"code": "代號", "name": "名稱", "sector": "產業別",
                 "market": "市場", "price": "現價",
                 "current_yield_pct": "目前殖利率%", "avg_5y_yield_pct": "平均5年殖利率%",
                 "latest_paid_year": "最新配年", "latest_paid_total_div": "最新總股利",
                 "business_nature": "主要業務"}.get(c, c)
                for c in watchlist_cols
            ]

            st.success(f"✅ 觀察清單已建立：**{filename}**（{len(wl)} 檔股票）")
            st.download_button(
                f"💾 下載觀察清單 {filename}",
                wl_export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                file_name=filename,
                mime="text/csv",
                type="primary",
            )
        else:
            st.info("👈 在左側設定殖利率門檻與日期，點擊「📋 Screen」即可建立觀察清單。")

    # ========== 個股詳情 ==========
    if not filtered.empty:
        st.markdown('<div class="section-header">🔍 個股詳情</div>', unsafe_allow_html=True)

        code_options = (filtered["code"].astype(str) + " — " + filtered["name"].astype(str)).tolist()
        selected = st.selectbox("選擇個股查看詳情", code_options, key="stock_select")
        selected_code = selected.split(" — ")[0].strip()

        row = filtered[filtered["code"].astype(str) == selected_code].iloc[0]
        sub = div_hist[div_hist["code"].astype(str) == selected_code].sort_values("year").copy()

        # 個股基本資訊
        if "sector" in row.index and row["sector"]:
            st.markdown(
                f'<div style="color:#8892a4; font-size:0.9rem; margin-bottom:4px;">'
                f'🏭 <strong style="color:#c0c8d4;">{row["sector"]}</strong>'
                + (f' &nbsp;|&nbsp; {row["business_nature"]}' if row.get("business_nature") else "")
                + "</div>",
                unsafe_allow_html=True,
            )

        # 個股 KPI
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("現價", f"${row['price']:.2f}")
        d2.metric("目前殖利率", f"{row['current_yield_pct']:.2f}%")
        d3.metric("平均 5 年殖利率", f"{row['avg_5y_yield_pct']:.2f}%")
        d4.metric("最新配息年度", str(int(row["latest_paid_year"])))

        # 圖表與明細
        left, right = st.columns([1, 1])

        with left:
            st.markdown("#### 📊 歷年股利明細")
            detail_df = sub[["year", "cash_div", "stock_div", "total_div"]].copy()
            detail_df.columns = ["年度", "現金股利", "股票股利", "合計"]
            st.dataframe(
                detail_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "年度": st.column_config.NumberColumn(format="%d"),
                    "現金股利": st.column_config.NumberColumn(format="%.2f"),
                    "股票股利": st.column_config.NumberColumn(format="%.2f"),
                    "合計": st.column_config.NumberColumn(format="%.2f"),
                },
            )

        with right:
            fig_trend = create_dividend_trend_chart(sub, str(row["code"]), str(row["name"]))
            st.plotly_chart(fig_trend, use_container_width=True)

        # 殖利率比較圖
        fig_yield = create_yield_comparison_chart(
            float(row["current_yield_pct"]),
            float(row["avg_5y_yield_pct"]),
        )
        st.plotly_chart(fig_yield, use_container_width=True)

    # ========== WILLIAMS VIX FIX 技術面掃描 ==========
    st.markdown('<div class="section-header">📡 技術面警示 — Williams VIX Fix</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="rule-box">
        <strong>📌 Williams VIX Fix 說明：</strong><br>
        模擬 VIX 恐慌指數，<strong style="color:#00D4AA;">綠色柱</strong> 代表近期出現恐慌底部訊號——
        當 WVF ≥ 布林上軌 <em>或</em> WVF ≥ 百分位高點時觸發。<br>
        本功能掃描觀察清單各股，找出 <strong>過去 3 個交易日</strong> 出現綠色訊號者，列為潛在買入提示。
    </div>
    """, unsafe_allow_html=True)

    # ── 選擇掃描來源 ──
    wl_session = st.session_state.get("watchlist_df")
    wl_meta    = st.session_state.get("watchlist_meta")

    src_options = []
    if wl_session is not None and not wl_session.empty:
        label = "目前觀察清單（session）"
        if wl_meta:
            label += f" — {wl_meta['date'].strftime('%d.%b.%Y')} · {len(wl_session)} 檔"
        src_options.append(label)
    src_options.append("上傳觀察清單 CSV")

    wvf_src = st.radio("📂 掃描來源", src_options, horizontal=True, key="wvf_src")

    wl_df: pd.DataFrame | None = None
    if wvf_src.startswith("目前觀察清單"):
        wl_df = wl_session
    else:
        uploaded = st.file_uploader(
            "上傳觀察清單 CSV（格式：TW_Div_xx_dd.mmm.yyyy.csv）",
            type=["csv"], key="wvf_upload",
        )
        if uploaded is not None:
            try:
                raw_csv = pd.read_csv(uploaded)
                # Map 繁體中文欄位 → 內部欄位名
                col_map = {"代號": "code", "名稱": "name", "產業別": "sector",
                           "市場": "market", "現價": "price",
                           "目前殖利率%": "current_yield_pct",
                           "平均5年殖利率%": "avg_5y_yield_pct"}
                raw_csv = raw_csv.rename(columns=col_map)
                raw_csv["code"] = raw_csv["code"].astype(str)
                if "market" not in raw_csv.columns:
                    raw_csv["market"] = "TWSE"   # fallback
                wl_df = raw_csv
                st.success(f"已載入：{uploaded.name}（{len(wl_df)} 檔股票）")
            except Exception as e:
                st.error(f"CSV 解析失敗：{e}")

    if wl_df is None or wl_df.empty:
        st.info("👈 請先建立觀察清單（點擊 Screen）或上傳 CSV，再執行掃描。")
    else:
        with st.expander("⚙️ 指標參數（選填，預設值與 Pine Script 原版相同）"):
            pc1, pc2, pc3 = st.columns(3)
            wvf_pd  = pc1.number_input("回望期 pd", 5, 50, 22, help="highest(close, pd) 的回望天數")
            wvf_bbl = pc2.number_input("BB 長度 bbl", 5, 50, 20, help="布林帶計算長度")
            wvf_mult= pc3.number_input("BB 倍數 mult", 0.5, 5.0, 2.0, 0.1, help="布林帶標準差倍數")
            pc4, pc5, pc6 = st.columns(3)
            wvf_lb  = pc4.number_input("百分位回望 lb", 10, 200, 50, help="highest/lowest 百分位的回望天數")
            wvf_ph  = pc5.number_input("高百分位 ph", 0.50, 1.00, 0.85, 0.01, help="rangeHigh = highest(wvf,lb) × ph")
            wvf_lkb = pc6.number_input("訊號掃描天數", 1, 7, 3, help="檢查最近幾個交易日是否出現綠色柱")

        scan_btn = st.button("📡 掃描（Williams VIX Fix）", use_container_width=True)

        if scan_btn:
            from technical import check_signal, make_wvf_chart

            stocks = wl_df[
                [c for c in ["code", "name", "sector", "market", "current_yield_pct", "avg_5y_yield_pct"] if c in wl_df.columns]
            ].to_dict("records")

            results = []
            bar = st.progress(0, text="掃描中…")
            for i, s in enumerate(stocks):
                sig = check_signal(
                    str(s["code"]), s.get("market", "TWSE"),
                    lookback_days=int(wvf_lkb),
                    pd_=int(wvf_pd), bbl=int(wvf_bbl), mult=float(wvf_mult),
                    lb=int(wvf_lb), ph=float(wvf_ph),
                )
                results.append({**s, **sig})
                bar.progress((i + 1) / len(stocks), text=f"掃描中… {s['code']} {s.get('name','')}")
            bar.empty()
            st.session_state["wvf_results"] = results
            st.session_state["wvf_lkb"] = int(wvf_lkb)

        # ---------- 顯示結果 ----------
        wvf_results = st.session_state.get("wvf_results")
        if wvf_results:
            from technical import make_wvf_chart

            green_hits = [r for r in wvf_results if r.get("green") and "error" not in r]
            no_signal  = [r for r in wvf_results if not r.get("green") and "error" not in r]
            errors     = [r for r in wvf_results if "error" in r]
            lkb = st.session_state.get("wvf_lkb", 3)

            if green_hits:
                st.markdown(
                    f'<div style="font-size:1.1rem; font-weight:700; color:#00D4AA; margin:16px 0 8px;">'
                    f'🟢 發現 {len(green_hits)} 檔潛在買入提示（近 {lkb} 日出現 WVF 綠色訊號）</div>',
                    unsafe_allow_html=True,
                )
                for r in green_hits:
                    code = str(r["code"])
                    name = r.get("name", "")
                    sector = r.get("sector", "")
                    cy = r.get("current_yield_pct", 0)
                    ay = r.get("avg_5y_yield_pct", 0)
                    days_hit = r.get("days", 0)
                    wvf_val = r.get("wvf", 0)
                    ub_val  = r.get("upper_band", 0)
                    rh_val  = r.get("range_high", 0)

                    st.markdown(f"""
                    <div style="
                        background:linear-gradient(135deg,#0d2a1f 0%,#1a3a2a 100%);
                        border:1px solid #00D4AA; border-left:5px solid #00D4AA;
                        border-radius:12px; padding:16px 20px; margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:1.15rem; font-weight:700; color:#e0e0e0;">
                                🟢 {code} &nbsp; {name}
                            </span>
                            <span style="font-size:0.82rem; color:#8892a4;">{sector}</span>
                        </div>
                        <div style="margin-top:8px; font-size:0.88rem; color:#b0b8c8;">
                            殖利率：<strong style="color:#00D4AA;">{cy:.2f}%</strong> &nbsp;｜&nbsp;
                            5年平均：<strong style="color:#00B4D8;">{ay:.2f}%</strong> &nbsp;｜&nbsp;
                            訊號：近 {lkb} 日中 <strong style="color:#00D4AA;">{days_hit} 日</strong> 出現綠色柱
                        </div>
                        <div style="margin-top:6px; font-size:0.82rem; color:#6b7b8d;">
                            WVF = {wvf_val:.2f} &nbsp;｜&nbsp;
                            Upper Band = {ub_val:.2f} &nbsp;｜&nbsp;
                            Range High = {rh_val:.2f}
                        </div>
                        <div style="margin-top:10px; font-size:0.85rem; color:#ffd700;">
                            ⚠️ 建議留意此股，Williams VIX Fix 顯示潛在市場恐慌底部，可評估是否買入。
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if r.get("wvf_data") is not None:
                        with st.expander(f"📊 {code} {name} — WVF 走勢圖"):
                            fig = make_wvf_chart(r, name)
                            st.plotly_chart(fig, use_container_width=True)

            else:
                st.info(f"近 {lkb} 個交易日內，觀察清單中無股票出現 WVF 綠色訊號。")

            # Summary table
            with st.expander(f"📋 全部掃描結果（{len(no_signal)} 股無訊號 / {len(errors)} 股無資料）"):
                rows = []
                for r in wvf_results:
                    rows.append({
                        "代號": r.get("code",""), "名稱": r.get("name",""),
                        "產業別": r.get("sector",""),
                        "訊號": "🟢 是" if r.get("green") else ("⚠️ 無資料" if "error" in r else "—"),
                        "觸發天數": r.get("days", 0) if "error" not in r else "-",
                        "WVF": r.get("wvf", "-") if "error" not in r else "-",
                        "Upper Band": r.get("upper_band", "-") if "error" not in r else "-",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ========== FOOTER ==========
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; color:#6b7b8d; font-size:0.8rem; padding:20px;">
        數據來源：TWSE/TPEX OpenAPI, Goodinfo.tw | 系統僅供參考，不構成任何投資建議。
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
