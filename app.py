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
from datetime import datetime
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

        # 下載 CSV
        csv_bytes = filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ 下載篩選結果 CSV",
            csv_bytes,
            file_name=f"tw_dividend_filtered_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

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

    # ========== FOOTER ==========
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; color:#6b7b8d; font-size:0.8rem; padding:20px;">
        數據來源：TWSE/TPEX OpenAPI, Goodinfo.tw | 系統僅供參考，不構成任何投資建議。
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
