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
    page_title="TW-DIV · Terminal",
    page_icon="▌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 自訂 CSS （Terminal / Bloomberg-inspired）---
st.markdown("""
<style>
    /* ─────────────  FONTS  ───────────── */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@200;400;500;700;800&family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

    :root {
        --bg:           #0A0D12;
        --bg-elev:      #12161D;
        --bg-hover:     #1A2028;
        --bg-panel:     #0E1219;
        --border:       #1F2936;
        --border-strong:#2B3542;
        --text:         #E5E7EB;
        --text-muted:   #9CA3AF;
        --text-dim:     #6B7280;
        --amber:        #FFB800;
        --amber-dim:    #A37700;
        --cyan:         #22D3EE;
        --cyan-dim:     #0E7C8F;
        --green:        #10B981;
        --red:          #EF4444;
        --purple:       #A78BFA;
        --mono:         'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        --cjk:          'Noto Sans TC', sans-serif;
    }

    /* ─── Global reset ─── */
    html, body, [class*="css"]  {
        font-family: var(--mono), var(--cjk);
        font-feature-settings: "tnum", "ss01", "cv11";
    }
    .stApp {
        background:
            radial-gradient(ellipse 90% 60% at 50% -10%, rgba(255,184,0,0.05) 0%, transparent 60%),
            radial-gradient(ellipse 70% 50% at 85% 100%, rgba(34,211,238,0.04) 0%, transparent 60%),
            var(--bg);
    }
    /* subtle scanline overlay */
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background-image: repeating-linear-gradient(
            0deg,
            rgba(255,255,255,0.012) 0px,
            rgba(255,255,255,0.012) 1px,
            transparent 1px,
            transparent 3px
        );
        z-index: 9999;
        mix-blend-mode: overlay;
    }

    /* Chinese characters use Noto Sans TC, latin/numbers stay mono */
    :lang(zh), :lang(zh-TW) { font-family: var(--cjk); }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }
    footer { visibility: hidden; }

    /* ─────────────  TERMINAL HEADER BAR  ───────────── */
    .term-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        margin: 0 0 18px 0;
        background: linear-gradient(180deg, #0E1219 0%, #0A0D12 100%);
        border: 1px solid var(--border);
        border-top: 2px solid var(--amber);
        border-radius: 2px;
        position: relative;
        overflow: hidden;
    }
    .term-header::after {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--amber), transparent);
        opacity: 0.6;
        animation: scan 8s linear infinite;
    }
    @keyframes scan {
        0%   { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    .term-brand {
        font-family: var(--mono);
        display: flex;
        align-items: baseline;
        gap: 14px;
    }
    .term-brand .brand {
        font-size: 1.35rem;
        font-weight: 800;
        color: var(--amber);
        letter-spacing: 0.08em;
    }
    .term-brand .brand .cursor {
        display: inline-block;
        width: 0.55em;
        height: 1em;
        background: var(--amber);
        vertical-align: -2px;
        margin-left: 4px;
        animation: blink 1.05s step-end infinite;
    }
    @keyframes blink { 50% { opacity: 0; } }
    .term-brand .slash {
        color: var(--text-dim);
        font-weight: 400;
    }
    .term-brand .tagline {
        color: var(--text-muted);
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }
    .term-header-right {
        display: flex;
        gap: 14px;
        align-items: center;
        font-family: var(--mono);
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .status-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border: 1px solid var(--border-strong);
        color: var(--text-muted);
        background: rgba(255,255,255,0.02);
    }
    .status-chip .dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: var(--green);
        box-shadow: 0 0 6px currentColor;
        animation: blink 1.4s ease-in-out infinite;
    }
    .status-chip.live { color: var(--green); border-color: rgba(16,185,129,0.4); }
    .status-chip.hist { color: var(--cyan); border-color: rgba(34,211,238,0.4); }
    .status-chip.hist .dot { background: var(--cyan); }
    .status-chip .kv-key { color: var(--text-dim); }
    .status-chip .kv-val { color: var(--text); font-weight: 500; }

    /* ─────────────  PROCEDURE · 4-STEP WORKFLOW  ───────────── */
    .procedure {
        border: 1px solid var(--border);
        background: var(--bg-panel);
        padding: 12px 16px;
        margin-bottom: 14px;
    }
    .procedure-head {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        font-family: var(--mono);
        font-size: 0.72rem;
    }
    .procedure-head .pt { color: var(--amber); }
    .procedure-head .title {
        color: var(--text);
        font-weight: 700;
        letter-spacing: 0.14em;
    }
    .procedure-head .hint {
        color: var(--text-dim);
        letter-spacing: 0.05em;
        margin-left: auto;
    }
    .procedure-steps {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 8px;
    }
    .step {
        padding: 12px 14px;
        border: 1px solid var(--border);
        background: rgba(255,255,255,0.01);
        font-family: var(--mono);
        transition: all 0.2s;
        display: flex;
        flex-direction: column;
        gap: 4px;
        position: relative;
    }
    .step .step-num {
        font-size: 0.66rem;
        font-weight: 500;
        color: var(--text-dim);
        letter-spacing: 0.18em;
        text-transform: uppercase;
    }
    .step .step-title {
        font-size: 0.98rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: 0.02em;
    }
    .step .step-sub {
        font-size: 0.72rem;
        color: var(--text-dim);
        line-height: 1.5;
        letter-spacing: 0.02em;
    }
    /* done: green check */
    .step.done {
        border-color: rgba(16,185,129,0.35);
        background: linear-gradient(180deg, rgba(16,185,129,0.05) 0%, transparent 100%);
    }
    .step.done .step-num { color: var(--green); }
    .step.done .step-num::before { content: "✓ "; color: var(--green); }
    .step.done .step-title { color: var(--text); }
    /* active: amber with glow */
    .step.active {
        border-color: var(--amber);
        background: linear-gradient(180deg, rgba(255,184,0,0.08) 0%, rgba(255,184,0,0.02) 100%);
        box-shadow:
            inset 3px 0 0 var(--amber),
            0 0 20px rgba(255,184,0,0.08);
    }
    .step.active .step-num {
        color: var(--amber);
        animation: blink 1.4s ease-in-out infinite;
    }
    .step.active .step-num::before {
        content: "▶ ";
        color: var(--amber);
    }
    .step.active .step-title { color: var(--amber); }
    /* pending: dim */
    .step.pending { opacity: 0.55; }
    .step.pending .step-title { color: var(--text-muted); }

    /* ─────────────  TICKER RULE STRIP  ───────────── */
    .ticker-strip {
        border: 1px solid var(--border);
        background: var(--bg-panel);
        padding: 10px 16px;
        margin-bottom: 18px;
        display: flex;
        flex-wrap: wrap;
        gap: 22px;
        align-items: center;
        font-family: var(--mono);
        font-size: 0.78rem;
        color: var(--text-muted);
    }
    .ticker-strip .pt { color: var(--amber); margin-right: 6px; }
    .ticker-strip .k  { color: var(--text-dim); letter-spacing: 0.08em; text-transform: uppercase; margin-right: 6px; }
    .ticker-strip .v  { color: var(--text); font-weight: 500; }
    .ticker-strip .warn{ color: var(--amber); }
    .ticker-strip .div{ color: var(--border-strong); margin: 0 2px; }

    /* ─────────────  KPI STRIP  ───────────── */
    .kpi-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        border: 1px solid var(--border);
        background:
            linear-gradient(180deg, rgba(255,184,0,0.02) 0%, transparent 100%),
            var(--bg-panel);
        margin: 8px 0 18px 0;
    }
    .kpi-cell {
        padding: 18px 20px;
        border-right: 1px solid var(--border);
        position: relative;
    }
    .kpi-cell:last-child { border-right: none; }
    .kpi-cell::before {
        content: "";
        position: absolute;
        top: 10px; left: 0;
        width: 3px; height: 18px;
        background: var(--amber);
        opacity: 0;
        transition: opacity 0.2s;
    }
    .kpi-cell:hover::before { opacity: 1; }
    .kpi-label {
        font-family: var(--mono);
        font-size: 0.68rem;
        font-weight: 500;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--text-dim);
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .kpi-label::before {
        content: "■";
        color: var(--amber);
        font-size: 0.6rem;
    }
    .kpi-value {
        font-family: var(--mono);
        font-size: 1.9rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.01em;
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }
    .kpi-value .unit {
        font-size: 0.75rem;
        color: var(--text-dim);
        font-weight: 400;
        margin-left: 4px;
        letter-spacing: 0.05em;
    }
    .kpi-value.amber { color: var(--amber); }
    .kpi-value.cyan  { color: var(--cyan); }
    .kpi-sub {
        margin-top: 4px;
        font-family: var(--mono);
        font-size: 0.72rem;
        color: var(--text-dim);
    }

    /* ─────────────  RULE PANEL  ───────────── */
    .rule-box {
        background: var(--bg-panel);
        border: 1px solid var(--border);
        border-left: 2px solid var(--cyan);
        padding: 14px 18px;
        margin-bottom: 14px;
        font-family: var(--mono);
        font-size: 0.8rem;
        color: var(--text-muted);
        line-height: 1.7;
    }
    .rule-box .lbl {
        color: var(--cyan);
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        font-size: 0.72rem;
        display: block;
        margin-bottom: 6px;
    }
    .rule-box code, .rule-box b, .rule-box strong {
        color: var(--text);
        background: rgba(255,184,0,0.08);
        padding: 1px 5px;
        border-radius: 2px;
    }
    .rule-box .rule-line { display: flex; gap: 8px; align-items: flex-start; }
    .rule-box .rule-line .ix { color: var(--amber); min-width: 1.5em; }

    /* ─────────────  SECTION HEADER  ───────────── */
    .section-header {
        font-family: var(--mono);
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: 0.18em;
        text-transform: uppercase;
        margin: 26px 0 14px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .section-header::before {
        content: ">_";
        color: var(--amber);
        font-weight: 800;
    }
    .section-header::after {
        content: "";
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, var(--border) 0%, transparent 100%);
        margin-left: 6px;
    }
    .section-header .count {
        color: var(--text-dim);
        font-weight: 400;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
    }

    /* ─────────────  SIDEBAR  ───────────── */
    [data-testid="stSidebar"] {
        background: var(--bg-panel);
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] > div {
        padding-top: 12px;
    }
    [data-testid="stSidebar"] h3 {
        font-family: var(--mono);
        font-size: 0.75rem !important;
        font-weight: 700;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: var(--amber);
        margin-bottom: 16px !important;
    }
    [data-testid="stSidebar"] label {
        font-family: var(--mono);
        font-size: 0.72rem !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted) !important;
        font-weight: 500 !important;
    }

    /* Data-status chip inside sidebar */
    .sb-status {
        background: linear-gradient(180deg, rgba(16,185,129,0.08) 0%, transparent 100%);
        border: 1px solid var(--border);
        border-left: 2px solid var(--green);
        padding: 10px 12px;
        margin-bottom: 12px;
        font-family: var(--mono);
    }
    .sb-status .k {
        font-size: 0.65rem;
        color: var(--text-dim);
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    .sb-status .v {
        font-size: 0.85rem;
        color: var(--green);
        font-weight: 700;
        margin: 2px 0;
    }
    .sb-status .t {
        font-size: 0.7rem;
        color: var(--text-muted);
    }

    /* ─────────────  WIDGETS  ───────────── */
    /* Buttons — terminal style */
    .stButton > button {
        font-family: var(--mono) !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        border-radius: 2px !important;
        border: 1px solid var(--border-strong) !important;
        background: var(--bg-elev) !important;
        color: var(--text) !important;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        border-color: var(--amber) !important;
        color: var(--amber) !important;
        background: rgba(255,184,0,0.06) !important;
        box-shadow: 0 0 0 1px var(--amber) inset;
    }
    .stButton > button[kind="primary"] {
        background: var(--amber) !important;
        color: #0A0D12 !important;
        border-color: var(--amber) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #FFCC33 !important;
        color: #0A0D12 !important;
        box-shadow: 0 0 12px rgba(255,184,0,0.4);
    }

    /* Download button */
    .stDownloadButton > button {
        font-family: var(--mono) !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        border-radius: 2px !important;
    }

    /* Inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput input {
        font-family: var(--mono) !important;
        background: var(--bg-elev) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 2px !important;
        color: var(--text) !important;
        font-variant-numeric: tabular-nums;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--amber) !important;
        box-shadow: 0 0 0 1px var(--amber) !important;
    }

    /* Select / Radio */
    [data-baseweb="select"] > div {
        background: var(--bg-elev) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 2px !important;
        font-family: var(--mono) !important;
    }
    .stRadio label {
        font-family: var(--mono);
    }

    /* Slider — amber accent */
    .stSlider [data-baseweb="slider"] > div > div {
        background: var(--border) !important;
    }
    .stSlider [role="slider"] {
        background: var(--amber) !important;
        box-shadow: 0 0 0 4px rgba(255,184,0,0.15) !important;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background: var(--bg-panel);
        border: 1px solid var(--border) !important;
        border-radius: 2px !important;
    }
    [data-testid="stExpander"] summary {
        font-family: var(--mono);
        letter-spacing: 0.08em;
        font-size: 0.8rem;
        color: var(--text-muted);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid var(--border);
        margin-bottom: 18px;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: var(--mono) !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.16em !important;
        text-transform: uppercase !important;
        color: var(--text-muted) !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        border-radius: 2px 2px 0 0 !important;
        padding: 10px 22px !important;
        margin-right: 2px;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text) !important;
        background: var(--bg-panel) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--amber) !important;
        border-color: var(--border) !important;
        border-bottom: 1px solid var(--bg) !important;
        background: var(--bg-panel) !important;
        position: relative;
    }
    .stTabs [aria-selected="true"]::before {
        content: "";
        position: absolute;
        top: -1px; left: 0; right: 0;
        height: 2px;
        background: var(--amber);
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none; }

    /* DataFrame / Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 2px;
    }
    [data-testid="stDataFrame"] table {
        font-family: var(--mono) !important;
        font-variant-numeric: tabular-nums;
    }

    /* Metric widget */
    [data-testid="stMetric"] {
        background: var(--bg-panel);
        border: 1px solid var(--border);
        padding: 12px 14px;
        border-radius: 2px;
        position: relative;
    }
    [data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        top: 0; left: 0;
        width: 2px; height: 100%;
        background: var(--amber);
        opacity: 0.5;
    }
    [data-testid="stMetricLabel"] {
        font-family: var(--mono) !important;
        font-size: 0.66rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase !important;
        color: var(--text-dim) !important;
    }
    [data-testid="stMetricValue"] {
        font-family: var(--mono) !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        font-variant-numeric: tabular-nums;
    }

    /* Alerts */
    [data-testid="stAlert"] {
        font-family: var(--mono);
        border-radius: 2px !important;
        border: 1px solid var(--border) !important;
        font-size: 0.82rem;
    }

    /* ─────────────  SIGNAL CARD  ───────────── */
    .sig-card {
        background: linear-gradient(90deg, rgba(16,185,129,0.08) 0%, var(--bg-panel) 30%);
        border: 1px solid var(--border);
        border-left: 3px solid var(--green);
        padding: 14px 18px;
        margin-bottom: 10px;
        font-family: var(--mono);
        position: relative;
    }
    .sig-card::after {
        content: "● 訊號";
        position: absolute;
        top: 10px; right: 14px;
        font-size: 0.65rem;
        letter-spacing: 0.2em;
        color: var(--green);
        animation: blink 1.8s ease-in-out infinite;
    }
    .sig-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 8px;
        padding-right: 80px;
    }
    .sig-code {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: 0.05em;
    }
    .sig-code .code-num { color: var(--amber); margin-right: 10px; }
    .sig-sector {
        font-size: 0.72rem;
        color: var(--text-dim);
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .sig-row {
        font-size: 0.8rem;
        color: var(--text-muted);
        margin-top: 4px;
    }
    .sig-row .k  { color: var(--text-dim); }
    .sig-row .v  { color: var(--text); font-weight: 500; }
    .sig-row .up { color: var(--green); }
    .sig-row .dn { color: var(--red); }
    .sig-row .bar-sep { color: var(--border-strong); margin: 0 8px; }
    .sig-flow {
        margin-top: 10px;
        padding: 8px 12px;
        background: rgba(255,255,255,0.02);
        border: 1px dashed var(--border);
        font-size: 0.76rem;
        color: var(--text-muted);
    }
    .sig-verdict {
        margin-top: 8px;
        font-size: 0.78rem;
        color: var(--text-muted);
        padding-left: 12px;
        border-left: 2px solid var(--amber);
    }

    /* Sector/business inline pill */
    .inline-pill {
        display: inline-block;
        padding: 2px 10px;
        font-family: var(--mono);
        font-size: 0.72rem;
        border: 1px solid var(--border-strong);
        color: var(--text-muted);
        letter-spacing: 0.08em;
        background: rgba(255,255,255,0.02);
        margin-right: 6px;
    }
    .inline-pill.amber { border-color: rgba(255,184,0,0.4); color: var(--amber); }

    /* Success/Info banner (for watchlist feedback) */
    .wl-banner {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 16px;
        margin: 12px 0;
        background: linear-gradient(90deg, rgba(16,185,129,0.08) 0%, transparent 100%);
        border: 1px solid var(--border);
        border-left: 2px solid var(--green);
        font-family: var(--mono);
        font-size: 0.82rem;
        color: var(--text);
    }
    .wl-banner .tag {
        color: var(--green);
        font-weight: 700;
        letter-spacing: 0.15em;
        font-size: 0.72rem;
    }
    .wl-banner .path {
        color: var(--amber);
        font-weight: 500;
    }

    /* Footer */
    .term-footer {
        margin-top: 32px;
        padding: 14px 0;
        border-top: 1px solid var(--border);
        font-family: var(--mono);
        font-size: 0.7rem;
        color: var(--text-dim);
        text-align: center;
        letter-spacing: 0.1em;
    }
    .term-footer .sep { color: var(--border-strong); margin: 0 8px; }
</style>
""", unsafe_allow_html=True)


# --- 路徑設定 ---
DATA_DIR = Path("data")
SCREENED_FILE = DATA_DIR / "screened_dataset.csv"
DIV_FILE      = DATA_DIR / "dividend_history.csv"
WATCHLIST_DIR = DATA_DIR / "watchlists"
WATCHLIST_MAX = 20

WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)


def _save_watchlist_csv(df: pd.DataFrame, filename: str) -> None:
    """Save watchlist CSV to WATCHLIST_DIR and prune to keep newest WATCHLIST_MAX files."""
    dest = WATCHLIST_DIR / filename
    df.to_csv(dest, index=False, encoding="utf-8-sig")
    # prune oldest if over limit
    existing = sorted(WATCHLIST_DIR.glob("TW_Div_*.csv"), key=lambda p: p.stat().st_mtime)
    for old in existing[:-WATCHLIST_MAX]:
        old.unlink(missing_ok=True)


def _list_watchlist_csvs() -> list[Path]:
    """Return saved watchlist CSVs sorted newest-first."""
    return sorted(WATCHLIST_DIR.glob("TW_Div_*.csv"),
                  key=lambda p: p.stat().st_mtime, reverse=True)[:WATCHLIST_MAX]


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


def render_kpi_cell(label: str, value: str, unit: str = "", accent: str = "",
                    sub: str = "") -> str:
    """Generate terminal-style KPI cell HTML.

    accent: "" | "amber" | "cyan" — controls value color.
    """
    klass = f"kpi-value {accent}".strip()
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    sub_html  = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi-cell">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="{klass}">{value}{unit_html}</div>'
        f'{sub_html}'
        f'</div>'
    )


def render_kpi_strip(cells_html: list[str]) -> str:
    """Wrap KPI cells in a single grid strip."""
    return f'<div class="kpi-strip">{"".join(cells_html)}</div>'


def create_dividend_trend_chart(sub: pd.DataFrame, code: str, name: str) -> go.Figure:
    """Terminal-styled dividend trend chart (stacked bars + total line)."""
    fig = go.Figure()

    # Cash dividend — cyan
    fig.add_trace(go.Bar(
        x=sub["year"],
        y=sub["cash_div"],
        name="CASH DIV",
        marker=dict(color="#22D3EE", line=dict(width=0)),
        opacity=0.95,
        hovertemplate="%{x}<br>CASH  %{y:.2f}<extra></extra>",
    ))

    # Stock dividend — purple
    fig.add_trace(go.Bar(
        x=sub["year"],
        y=sub["stock_div"],
        name="STOCK DIV",
        marker=dict(color="#A78BFA", line=dict(width=0)),
        opacity=0.95,
        hovertemplate="%{x}<br>STOCK %{y:.2f}<extra></extra>",
    ))

    # Total line — amber
    fig.add_trace(go.Scatter(
        x=sub["year"],
        y=sub["total_div"],
        name="TOTAL",
        mode="lines+markers",
        line=dict(color="#FFB800", width=2, shape="linear"),
        marker=dict(size=7, color="#FFB800",
                    line=dict(color="#0A0D12", width=1.5)),
        hovertemplate="%{x}<br>TOTAL %{y:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"  {code} · {name.upper()} / DIVIDEND HISTORY",
            font=dict(size=12, color="#9CA3AF",
                      family="JetBrains Mono, monospace"),
            x=0, xanchor="left", y=0.96,
        ),
        xaxis=dict(
            title=dict(text="YEAR",
                       font=dict(size=10, color="#6B7280",
                                 family="JetBrains Mono, monospace")),
            dtick=1,
            gridcolor="rgba(255,255,255,0.03)",
            linecolor="#1F2936",
            tickfont=dict(family="JetBrains Mono, monospace",
                          size=10, color="#9CA3AF"),
            showspikes=True, spikecolor="#FFB800",
            spikethickness=1, spikedash="dot",
        ),
        yaxis=dict(
            title=dict(text="DIVIDEND (TWD)",
                       font=dict(size=10, color="#6B7280",
                                 family="JetBrains Mono, monospace")),
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="#1F2936",
            tickfont=dict(family="JetBrains Mono, monospace",
                          size=10, color="#9CA3AF"),
            zerolinecolor="#1F2936",
        ),
        barmode="stack",
        plot_bgcolor="#0E1219",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9CA3AF", family="JetBrains Mono, monospace"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(family="JetBrains Mono, monospace",
                      size=10, color="#9CA3AF"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=50, r=20, t=56, b=44),
        height=380,
        hoverlabel=dict(bgcolor="#0A0D12",
                        bordercolor="#FFB800",
                        font=dict(family="JetBrains Mono, monospace",
                                  color="#E5E7EB", size=11)),
    )
    return fig


def create_yield_comparison_chart(current_yield: float, avg_5y: float) -> go.Figure:
    """Terminal-styled horizontal yield comparison."""
    fig = go.Figure()

    categories = ["CUR YLD", "5Y AVG"]
    values = [current_yield, avg_5y]
    colors = ["#FFB800", "#22D3EE"]

    fig.add_trace(go.Bar(
        y=categories,
        x=values,
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:.2f}%" for v in values],
        textposition="outside",
        textfont=dict(size=12, color="#E5E7EB",
                      family="JetBrains Mono, monospace"),
        hovertemplate="%{y} · %{x:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="  YIELD COMPARISON",
            font=dict(size=12, color="#9CA3AF",
                      family="JetBrains Mono, monospace"),
            x=0, xanchor="left", y=0.95,
        ),
        xaxis=dict(
            title=dict(text="YIELD (%)",
                       font=dict(size=10, color="#6B7280",
                                 family="JetBrains Mono, monospace")),
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="#1F2936",
            tickfont=dict(family="JetBrains Mono, monospace",
                          size=10, color="#9CA3AF"),
            zerolinecolor="#1F2936",
        ),
        yaxis=dict(
            autorange="reversed",
            linecolor="#1F2936",
            tickfont=dict(family="JetBrains Mono, monospace",
                          size=11, color="#E5E7EB"),
        ),
        plot_bgcolor="#0E1219",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9CA3AF", family="JetBrains Mono, monospace"),
        margin=dict(l=10, r=40, t=50, b=44),
        height=220,
        showlegend=False,
        hoverlabel=dict(bgcolor="#0A0D12",
                        bordercolor="#FFB800",
                        font=dict(family="JetBrains Mono, monospace",
                                  color="#E5E7EB")),
    )
    return fig


# ============================================================
#  主程式
# ============================================================

def main():
    # --- Data freshness / universe size (needed in header) ---
    _freshness = get_data_freshness()

    # --- 檢查資料檔 ---
    if not SCREENED_FILE.exists() or not DIV_FILE.exists():
        st.error("⚠️ 找不到資料檔！請先執行 `python build_dataset.py` 建置資料。")
        st.code("python build_dataset.py", language="bash")
        st.stop()

    screened, div_hist = load_data()
    _universe = len(screened)

    # --- Determine current workflow step ---
    _wl_exists      = st.session_state.get("watchlist_df") is not None
    _wvf_has_result = st.session_state.get("wvf_results") is not None
    if _wvf_has_result:
        _active_step = 4
    elif _wl_exists:
        _active_step = 3
    else:
        _active_step = 1   # waiting on user to pick date & screen

    # --- TERMINAL HEADER ---
    st.markdown(f"""
    <div class="term-header">
        <div class="term-brand">
            <span class="brand">TW-DIV<span class="cursor"></span></span>
            <span class="slash">//</span>
            <span class="tagline">台股股利智能選股 · 終端機</span>
        </div>
        <div class="term-header-right">
            <span class="status-chip live">
                <span class="dot"></span>即時
            </span>
            <span class="status-chip">
                <span class="kv-key">同步</span>
                <span class="kv-val">{_freshness}</span>
            </span>
            <span class="status-chip">
                <span class="kv-key">母體</span>
                <span class="kv-val">{_universe:03d}</span>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- PROCEDURE · 4-STEP WORKFLOW ---
    def _step(n: int, title: str, sub: str, active: int) -> str:
        state = "done" if n < active else ("active" if n == active else "pending")
        return (
            f'<div class="step {state}">'
            f'<div class="step-num">步驟 {n:02d}</div>'
            f'<div class="step-title">{title}</div>'
            f'<div class="step-sub">{sub}</div>'
            f'</div>'
        )
    _steps_html = (
        _step(1, "選擇日期",        "左側欄 · 設定觀察日期與殖利率門檻", _active_step)
        + _step(2, "建立 CSV 清單",  "點擊 [ 執行選股 ] · 自動儲存觀察清單", _active_step)
        + _step(3, "選擇 CSV",       "WVF 區 · 選擇來源（session／檔案／上傳）", _active_step)
        + _step(4, "執行 WVF 掃描",  "點擊 [ 執行掃描 ] · 查看綠色底部訊號", _active_step)
    )
    st.markdown(f"""
    <div class="procedure">
        <div class="procedure-head">
            <span class="pt">▸</span>
            <span class="title">使用流程 · PROCEDURE</span>
            <span class="hint">依序執行 · 當前進度：步驟 {_active_step:02d} / 04</span>
        </div>
        <div class="procedure-steps">{_steps_html}</div>
    </div>
    """, unsafe_allow_html=True)

    # --- TICKER STRIP — rules as a single scanning line ---
    st.markdown("""
    <div class="ticker-strip">
        <span><span class="pt">▸</span><span class="k">篩選規則</span>
            <span class="v">連續 10 年配息</span>
            <span class="div">│</span>
            <span class="v">目前殖利率 ≥ X</span>
            <span class="div">│</span>
            <span class="v">5 年平均殖利率 ≥ Y</span>
        </span>
        <span><span class="k">觀察期間</span><span class="v">2016 — 2025</span></span>
        <span><span class="k">公式</span><span class="v">（現金 + 股票股利）÷ 現價</span></span>
        <span class="warn">⚠ 非標準定義：含股票股利</span>
    </div>
    """, unsafe_allow_html=True)

    # ========== SIDEBAR ==========
    with st.sidebar:
        st.markdown("### ▌ 控制面板 · 篩選參數")

        # Data status chip
        st.markdown(f"""
        <div class="sb-status">
            <div class="k">資料狀態</div>
            <div class="v">● 離線預建 · 正常</div>
            <div class="t">最後同步 · {_freshness}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("↻ 清除快取 · 重新載入", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        min_current = st.slider(
            "目前殖利率 ≥ (%)",
            min_value=0.0, max_value=20.0, value=4.0, step=0.1,
            help="目前殖利率最低門檻"
        )
        min_avg5 = st.slider(
            "5 年平均殖利率 ≥ (%)",
            min_value=0.0, max_value=20.0, value=4.0, step=0.1,
            help="近 5 年平均殖利率最低門檻"
        )

        st.divider()

        market = st.radio(
            "市場別",
            ["全部", "上市 (TWSE)", "上櫃 (TPEX)"],
            index=0
        )

        sort_by = st.selectbox(
            "排序方式",
            ["平均 5 年殖利率 ↓", "目前殖利率 ↓", "股票代號 ↑"]
        )

        st.divider()

        # Watchlist date + Screen button
        today = date.today()
        watchlist_date = st.date_input(
            "觀察日期 · AS-OF",
            value=st.session_state.get("watchlist_date", today),
            min_value=today.replace(year=today.year - 10),
            max_value=today,
            help="標記此觀察清單的日期。變更日期後需重新點擊 [ 執行選股 ]。",
            key="watchlist_date_input",
        )
        apply_btn = st.button("▶ 執行選股 · 建立觀察清單",
                              use_container_width=True, type="primary")

        # Show last screen summary
        meta = st.session_state.get("watchlist_meta")
        if meta:
            prev_date = meta["date"].strftime("%d.%b.%Y")
            prev_n = len(st.session_state.get("watchlist_df", []))
            st.markdown(
                f'<div style="font-size:0.7rem; color:#6B7280; padding:6px 2px; '
                f'font-family:JetBrains Mono,monospace; letter-spacing:0.05em;">'
                f'<span style="color:#FFB800;">›</span> 上次 · {prev_date} · '
                f'<span style="color:#E5E7EB;">{prev_n}</span> 檔 · '
                f'殖利率 ≥ {meta["min_current"]:.1f}%</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown("""
        <div style="font-family:JetBrains Mono,monospace; font-size:0.72rem;
                    color:#9CA3AF; line-height:1.75; padding:6px 2px;">
            <div style="color:#FFB800; font-weight:700; letter-spacing:0.14em;
                        margin-bottom:4px;">› 提示 · 資料更新</div>
            Goodinfo 限制雲端抓取。請於本機執行
            <code style="color:#22D3EE;">build_dataset.py</code>，
            推送至 GitHub 後即可更新雲端資料。
        </div>
        <div style="font-family:JetBrains Mono,monospace; font-size:0.72rem;
                    color:#9CA3AF; line-height:1.75; padding:6px 2px; margin-top:12px;">
            <div style="color:#FFB800; font-weight:700; letter-spacing:0.14em;
                        margin-bottom:4px;">› 提示 · 殖利率定義</div>
            本系統殖利率 = 現金股利 + 股票股利<br>
            與市場常見「現金殖利率」不同。
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
                sub_d = sub_d[sub_d["year"] <= target_year]
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

            if not hist_prices:
                st.error("❌ 無法從 yfinance 取得歷史股價，請確認網路連線或稍後重試。")
                st.session_state["watchlist_df"] = filtered.copy()
            elif not rows:
                st.warning(f"⚠️ 取得 {len(hist_prices)} 檔股價，但所有股票在 {target_date} 均無股利資料可計算，已改用當前資料。")
                st.session_state["watchlist_df"] = filtered.copy()
            else:
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
                st.success(f"✅ 歷史篩選完成：{len(hist_prices)} 檔取得股價 → 符合條件 {len(hist_filtered)} 檔")
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

    # ========== 決定主要顯示資料來源 ==========
    # 若已用歷史日期 Screen 過，主畫面改用當時的歷史結果；否則沿用即時篩選
    _wl = st.session_state.get("watchlist_df")
    _meta = st.session_state.get("watchlist_meta")
    _is_historical = (
        _wl is not None
        and _meta is not None
        and _meta["date"] < date.today()
    )
    if _is_historical:
        _wl_view = _wl[
            (_wl["current_yield_pct"] >= min_current) &
            (_wl["avg_5y_yield_pct"]  >= min_avg5)
        ].copy()
        if market == "上市 (TWSE)":
            _wl_view = _wl_view[_wl_view["market"] == "TWSE"]
        elif market == "上櫃 (TPEX)":
            _wl_view = _wl_view[_wl_view["market"] == "TPEX"]
        sort_cols_v, sort_asc_v = sort_map[sort_by]
        _wl_view = _wl_view.sort_values(sort_cols_v, ascending=sort_asc_v).reset_index(drop=True)
        display_df = _wl_view
        _date_label = _meta["date"].strftime("%d.%b.%Y")
    else:
        display_df = filtered
        _date_label = None

    # ========== 歷史模式提示橫幅 ==========
    if _is_historical:
        _b1, _b2 = st.columns([5, 1])
        with _b1:
            st.markdown(
                f'<div style="background:linear-gradient(90deg,rgba(34,211,238,0.08) 0%,transparent 100%);'
                f'border:1px solid #1F2936;border-left:2px solid #22D3EE;padding:10px 16px;'
                f'font-family:JetBrains Mono,monospace;font-size:0.82rem;color:#9CA3AF;">'
                f'<span style="color:#22D3EE;font-weight:700;letter-spacing:0.15em;">◷ 歷史模式</span>'
                f' &nbsp;觀察日期 <strong style="color:#E5E7EB;">{_date_label}</strong>'
                f' · 門檻 <strong style="color:#FFB800;">≥ {_meta["min_current"]:.1f}%</strong>'
                f' &nbsp;<span style="color:#6B7280;">— 變更門檻後需重新 [ 執行選股 ]</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _b2:
            if st.button("✖ 回即時", help="清除歷史篩選結果 · 回到即時資料",
                         use_container_width=True):
                st.session_state.pop("watchlist_df", None)
                st.session_state.pop("watchlist_meta", None)
                st.session_state.pop("wvf_results", None)
                st.rerun()

    # ========== KPI STRIP ==========
    _n_hits   = len(display_df)
    _hit_rate = (_n_hits / _universe * 100) if _universe else 0
    if not display_df.empty:
        _avg_cur = f"{display_df['current_yield_pct'].mean():.2f}"
        _avg_5y  = f"{display_df['avg_5y_yield_pct'].mean():.2f}"
        _max_cur = f"{display_df['current_yield_pct'].max():.2f}"
    else:
        _avg_cur = _avg_5y = _max_cur = "—"

    _kpi_cells = [
        render_kpi_cell(
            "符合檔數 · MATCHES",
            f"{_n_hits:03d}",
            accent="amber",
            sub=f"佔母體 {_hit_rate:.1f}%",
        ),
        render_kpi_cell(
            "平均目前殖利率",
            _avg_cur,
            unit="%" if _avg_cur != "—" else "",
            accent="",
            sub="算術平均 · 已篩選",
        ),
        render_kpi_cell(
            "5 年平均殖利率",
            _avg_5y,
            unit="%" if _avg_5y != "—" else "",
            accent="cyan",
            sub="5 年算術平均",
        ),
        render_kpi_cell(
            "最高殖利率",
            _max_cur,
            unit="%" if _max_cur != "—" else "",
            accent="amber",
            sub="篩選集 · 最大值",
        ),
    ]
    st.markdown(render_kpi_strip(_kpi_cells), unsafe_allow_html=True)

    # ========== 股票清單 ==========
    _list_title = "選股結果 · 觀察清單" + (f" · {_date_label}" if _date_label else "")
    _count_badge = f'<span class="count">{len(display_df):03d} 檔</span>'
    st.markdown(
        f'<div class="section-header">{_list_title}{_count_badge}</div>',
        unsafe_allow_html=True,
    )

    if display_df.empty:
        st.info("🔍 目前沒有符合條件的股票，請嘗試調低殖利率門檻。")
    else:
        # 表格欄位設定
        base_cols = [
            "code", "name", "sector", "business_nature", "price",
            "latest_paid_year", "latest_paid_total_div",
            "current_yield_pct", "sum_5y_div", "avg_5y_yield_pct",
        ]
        # 相容舊 CSV（若尚未重建資料，sector/business_nature 欄可能不存在）
        table_cols = [c for c in base_cols if c in display_df.columns]
        table_df = display_df[table_cols].copy()
        col_name_map = {
            "code": "代號", "name": "名稱",
            "sector": "產業別", "business_nature": "主要業務",
            "price": "現價",
            "latest_paid_year": "最新配年", "latest_paid_total_div": "最新總股利",
            "current_yield_pct": "目前殖利率%", "sum_5y_div": "近5年總股利",
            "avg_5y_yield_pct": "平均5年殖利率%",
        }
        table_df.columns = [col_name_map[c] for c in table_cols]

        st.dataframe(
            table_df,
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
            height=min(400, 40 + len(table_df) * 35),
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

            # Auto-save to watchlists folder
            _save_watchlist_csv(wl_export, filename)

            st.markdown(
                f'<div class="wl-banner">'
                f'<span class="tag">✔ 寫入成功</span>'
                f'<span>觀察清單已建立 → <span class="path">{filename}</span> '
                f'· <span style="color:#FFB800;">{len(wl):03d}</span> 檔</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                f"⇩ 下載觀察清單 · {filename}",
                wl_export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                file_name=filename,
                mime="text/csv",
                type="primary",
            )
        else:
            st.info("◁ 請於左側設定殖利率門檻與觀察日期，點擊 [ 執行選股 ] 建立觀察清單。")

    # ========== 個股詳情 ==========
    if not display_df.empty:
        st.markdown(
            '<div class="section-header">個股深度分析 · 深入檢視</div>',
            unsafe_allow_html=True,
        )

        code_options = (display_df["code"].astype(str) + " — " + display_df["name"].astype(str)).tolist()
        selected = st.selectbox("選擇個股", code_options, key="stock_select")
        selected_code = selected.split(" — ")[0].strip()

        row = display_df[display_df["code"].astype(str) == selected_code].iloc[0]
        sub = div_hist[div_hist["code"].astype(str) == selected_code].sort_values("year").copy()

        # 個股基本資訊 — sector/business as inline pills
        if "sector" in row.index and row["sector"]:
            import html as _html
            _sec = _html.escape(str(row["sector"]))
            _biz = _html.escape(str(row.get("business_nature", "") or ""))
            _pills = f'<span class="inline-pill amber">▸ {_sec}</span>'
            if _biz:
                _pills += f'<span class="inline-pill">{_biz}</span>'
            st.markdown(
                f'<div style="margin:6px 0 14px 0;">{_pills}</div>',
                unsafe_allow_html=True,
            )

        # 個股 KPI
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("現價 · TWD", f"{row['price']:.2f}")
        d2.metric("目前殖利率 %", f"{row['current_yield_pct']:.2f}")
        d3.metric("5 年平均 %", f"{row['avg_5y_yield_pct']:.2f}")
        d4.metric("最新配息年度", str(int(row["latest_paid_year"])))

        # 圖表與明細
        left, right = st.columns([1, 1])

        with left:
            st.markdown(
                '<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                'font-weight:700;letter-spacing:0.16em;'
                'color:#9CA3AF;margin:10px 0 8px 0;">›&nbsp; 歷年股利明細</div>',
                unsafe_allow_html=True,
            )
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
    st.markdown(
        '<div class="section-header">技術訊號 · WILLIAMS VIX FIX</div>',
        unsafe_allow_html=True,
    )

    st.markdown("""
    <div class="rule-box">
        <span class="lbl">▸ WVF · Williams VIX Fix 說明</span>
        <div class="rule-line"><span class="ix">01</span><span>以股價歷史合成類 VIX 的恐慌代理指標。</span></div>
        <div class="rule-line"><span class="ix">02</span><span><strong>綠色柱</strong> 於 <strong>WVF ≥ 布林上軌</strong> <em>或</em> <strong>WVF ≥ 百分位高點</strong> 時觸發 — 代表恐慌底部訊號。</span></div>
        <div class="rule-line"><span class="ix">03</span><span>本掃描器針對觀察清單個股，找出最近 <strong>3 個交易日</strong> 出現 ≥ 1 支綠色柱者 — 列為潛在買進候選。</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Select scan source ──
    wl_session = st.session_state.get("watchlist_df")
    wl_meta    = st.session_state.get("watchlist_meta")

    _saved_csvs = _list_watchlist_csvs()

    src_options = []
    if wl_session is not None and not wl_session.empty:
        label = "目前觀察清單（session）"
        if wl_meta:
            label += f" — {wl_meta['date'].strftime('%d.%b.%Y')} · {len(wl_session)} 檔"
        src_options.append(label)
    if _saved_csvs:
        src_options.append("已儲存觀察清單 CSV")
    src_options.append("上傳觀察清單 CSV")

    wvf_src = st.radio("掃描來源", src_options, horizontal=True, key="wvf_src")

    _col_map = {"代號": "code", "名稱": "name", "產業別": "sector",
                "市場": "market", "現價": "price",
                "目前殖利率%": "current_yield_pct",
                "平均5年殖利率%": "avg_5y_yield_pct"}

    def _load_csv_df(p: Path) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(p)
            df = df.rename(columns=_col_map)
            df["code"] = df["code"].astype(str)
            if "market" not in df.columns:
                df["market"] = "TWSE"
            return df
        except Exception as e:
            st.error(f"CSV 解析失敗：{e}")
            return None

    wl_df: pd.DataFrame | None = None
    if wvf_src.startswith("目前觀察清單"):
        wl_df = wl_session
    elif wvf_src == "已儲存觀察清單 CSV":
        _csv_names = [p.name for p in _saved_csvs]
        _sel_name = st.selectbox(
            "選擇觀察清單",
            _csv_names,
            key="wvf_saved_sel",
        )
        if _sel_name:
            _sel_path = WATCHLIST_DIR / _sel_name
            wl_df = _load_csv_df(_sel_path)
            if wl_df is not None:
                st.success(f"已載入：{_sel_name}（{len(wl_df)} 檔股票）")
    else:
        uploaded = st.file_uploader(
            "上傳觀察清單 CSV（格式：TW_Div_xx_dd.mmm.yyyy.csv）",
            type=["csv"], key="wvf_upload",
        )
        if uploaded is not None:
            try:
                raw_csv = pd.read_csv(uploaded)
                raw_csv = raw_csv.rename(columns=_col_map)
                raw_csv["code"] = raw_csv["code"].astype(str)
                if "market" not in raw_csv.columns:
                    raw_csv["market"] = "TWSE"
                wl_df = raw_csv
                st.success(f"已載入：{uploaded.name}（{len(wl_df)} 檔股票）")
            except Exception as e:
                st.error(f"CSV 解析失敗：{e}")

    if wl_df is None or wl_df.empty:
        st.info("◁ 請先建立觀察清單（步驟 02）或上傳 CSV（步驟 03），再執行掃描。")
    else:
        with st.expander("⚙ 指標參數（選填 · 預設值與 Pine Script 原版相同）"):
            pc1, pc2, pc3 = st.columns(3)
            wvf_pd  = pc1.number_input("回望期 pd", 5, 50, 22, help="highest(close, pd) 的回望天數")
            wvf_bbl = pc2.number_input("BB 長度 bbl", 5, 50, 20, help="布林帶計算長度")
            wvf_mult= pc3.number_input("BB 倍數 mult", 0.5, 5.0, 2.0, 0.1, help="布林帶標準差倍數")
            pc4, pc5, pc6 = st.columns(3)
            wvf_lb  = pc4.number_input("百分位回望 lb", 10, 200, 50, help="highest/lowest 百分位的回望天數")
            wvf_ph  = pc5.number_input("高百分位 ph", 0.50, 1.00, 0.85, 0.01, help="rangeHigh = highest(wvf,lb) × ph")
            wvf_lkb = pc6.number_input("訊號掃描天數", 1, 7, 3, help="檢查最近幾個交易日是否出現綠色柱")


        # ── 📡 Action Criteria ───────────────────────────────────────────
        st.markdown(
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            'color:#9CA3AF;letter-spacing:0.12em;text-transform:uppercase;'
            'border-left:2px solid #FFB800;padding:4px 0 4px 10px;'
            'margin:14px 0 8px 0;">📡 Action Criteria · 觸發條件（全部選填）</div>',
            unsafe_allow_html=True,
        )
        _crit_left, _crit_right = st.columns([1, 3])
        with _crit_left:
            use_wvf_crit = st.checkbox(
                "WVF 底部訊號",
                value=True,
                help="近 N 個交易日出現 WVF 綠色訊號（恐慌底部）",
                key="act_wvf",
            )
        with _crit_right:
            st.markdown(
                '<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;'
                'color:#6B7280;padding-bottom:4px;">SMA 均線 · 收盤需在均線之上</div>',
                unsafe_allow_html=True,
            )
            _sma_cols = st.columns(4)
            sma_use_10  = _sma_cols[0].checkbox("SMA 10",  value=False, key="act_sma10")
            sma_use_20  = _sma_cols[1].checkbox("SMA 20",  value=False, key="act_sma20")
            sma_use_60  = _sma_cols[2].checkbox("SMA 60",  value=False, key="act_sma60")
            sma_use_200 = _sma_cols[3].checkbox("SMA 200", value=False, key="act_sma200")

        sma_periods_selected = [
            p for p, on in [
                (10, sma_use_10), (20, sma_use_20),
                (60, sma_use_60), (200, sma_use_200),
            ] if on
        ]

        scan_btn = st.button("▶ 執行技術掃描", use_container_width=True, type="primary")

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
                    sma_periods=sma_periods_selected,
                )
                results.append({**s, **sig})
                bar.progress((i + 1) / len(stocks), text=f"掃描中… {s['code']} {s.get('name','')}")
            bar.empty()
            st.session_state["wvf_results"]      = results
            st.session_state["wvf_lkb"]          = int(wvf_lkb)
            st.session_state["wvf_sma_periods"]  = sma_periods_selected
            st.session_state["wvf_use_wvf_crit"] = use_wvf_crit

        # ---------- 顯示結果 ----------
        wvf_results = st.session_state.get("wvf_results")
        if wvf_results:
            from technical import make_wvf_chart

            lkb              = st.session_state.get("wvf_lkb", 3)
            use_wvf_crit     = st.session_state.get("wvf_use_wvf_crit", True)
            sma_periods_disp = st.session_state.get("wvf_sma_periods", [])

            # Apply filters based on Action Criteria
            def _passes(r: dict) -> bool:
                if "error" in r:
                    return False
                # WVF criterion
                if use_wvf_crit and not r.get("green"):
                    return False
                # Multi-SMA: ALL selected periods must be above
                if sma_periods_disp:
                    sma_checks = r.get("sma_checks", {})
                    for p in sma_periods_disp:
                        chk = sma_checks.get(p, {})
                        if chk.get("above") is False:
                            return False
                return True

            green_hits = [r for r in wvf_results if _passes(r)]
            no_signal  = [r for r in wvf_results if not _passes(r) and "error" not in r]
            errors     = [r for r in wvf_results if "error" in r]

            # Active criteria info banner
            _active_criteria = []
            if use_wvf_crit:
                _active_criteria.append(f"WVF 底部訊號（近 {lkb} 日）")
            for p in sma_periods_disp:
                _active_criteria.append(f"收盤 > SMA{p}")
            if _active_criteria:
                st.info("✅ 已啟用篩選條件：" + " ＋ ".join(_active_criteria))

            if green_hits:
                st.markdown(
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.82rem;'
                    f'font-weight:700;letter-spacing:0.12em;'
                    f'color:#10B981;margin:18px 0 10px 0;">'
                    f'● 發現 {len(green_hits):03d} 檔 · 恐慌底部候選 · '
                    f'回看 {lkb} 日</div>',
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

                    sma_checks = r.get("sma_checks", {})
                    last_close = r.get("last_close")
                    ma_row = ""
                    if sma_checks and last_close is not None:
                        badges = []
                        for p in sorted(sma_checks.keys()):
                            chk = sma_checks[p]
                            sma_v = chk.get("sma")
                            ab    = chk.get("above")
                            if sma_v is None or ab is None:
                                badges.append(f'<span style="color:#6B7280;">SMA{p} 資料不足</span>')
                            elif ab:
                                badges.append(f'<span class="up">▲ &gt; SMA{p} {sma_v}</span>')
                            else:
                                badges.append(f'<span class="dn">▼ &lt; SMA{p} {sma_v}</span>')
                        if badges:
                            ma_row = (
                                f'<div class="sig-row">'
                                f'<span class="k">收盤 {last_close}</span> '
                                + ' <span class="bar-sep">│</span> '.join(badges)
                                + '</div>'
                            )
                    elif r.get("above_ma") is not None and last_close is not None:
                        # legacy single-MA fallback
                        ma_label = r.get("ma_label", "MA")
                        last_ma  = r.get("last_ma")
                        above_ma = r.get("above_ma")
                        ma_badge = (
                            f'<span class="up">▲ 收盤 {last_close} &gt; {ma_label} {last_ma}</span>'
                            if above_ma else
                            f'<span class="dn">▼ 收盤 {last_close} &lt; {ma_label} {last_ma}</span>'
                        )
                        ma_row = f'<div class="sig-row">{ma_badge}</div>'

                    import html as _html
                    _name_s   = _html.escape(str(name))
                    _sector_s = _html.escape(str(sector)) if sector else ""

                    # Fetch 三大法人 data
                    from technical import fetch_institutional_flow
                    _flow = fetch_institutional_flow(code, days=60)

                    def _fmt_net(v: int) -> str:
                        return f'<span class="up">▲ +{v:,}</span>' if v >= 0 else f'<span class="dn">▼ {v:,}</span>'

                    if _flow:
                        _f, _t, _d, _tot = _flow["foreign"], _flow["trust"], _flow["dealer"], _flow["total"]
                        _n = _flow["days"]
                        _inst_row = (
                            f'<div class="sig-flow">'
                            f'<span style="color:#6B7280;letter-spacing:0.1em;font-size:0.7rem;">'
                            f'三大法人 · 近 {_n} 日（張）</span><br>'
                            f'<span class="k">外資</span> {_fmt_net(_f)} '
                            f'<span class="bar-sep">│</span> '
                            f'<span class="k">投信</span> {_fmt_net(_t)} '
                            f'<span class="bar-sep">│</span> '
                            f'<span class="k">自營商</span> {_fmt_net(_d)} '
                            f'<span class="bar-sep">│</span> '
                            f'<span class="k">合計</span> <strong>{_fmt_net(_tot)}</strong>'
                            f'</div>'
                        )
                        # Verdict
                        if _tot > 0 and days_hit >= 2:
                            _verdict = ('▶ <strong style="color:#10B981;">法人合計買超，與 WVF 底部訊號一致</strong>'
                                        ' — 可列為重點觀察，評估進場時機。')
                        elif _tot > 0:
                            _verdict = ('▶ 法人小幅買超，WVF 出現底部訊號 — '
                                        '<strong style="color:#E5E7EB;">建議關注後續量能</strong>。')
                        elif _tot < 0 and abs(_tot) > 1000:
                            _verdict = ('▶ <strong style="color:#EF4444;">法人明顯賣超</strong>'
                                        ' · 資金面偏空，WVF 訊號雖現，建議 '
                                        '<strong style="color:#FFB800;">暫觀</strong>，待賣壓減輕再評估。')
                        else:
                            _verdict = '▶ 法人動向中性 · WVF 底部訊號僅供參考，建議觀察量價配合再決策。'
                        _verdict_row = f'<div class="sig-verdict">{_verdict}</div>'
                    else:
                        _inst_row = (
                            '<div class="sig-flow" style="color:#6B7280;">'
                            '三大法人 · 資料暫無法取得（FinMind API）'
                            '</div>'
                        )
                        _verdict_row = (
                            '<div class="sig-verdict" style="border-left-color:#FFB800;">'
                            '⚠ WVF 顯示恐慌底部訊號 · 請自行查閱法人動向後評估。'
                            '</div>'
                        )

                    # Build card
                    _card = (
                        '<div class="sig-card">'
                        '<div class="sig-head">'
                        f'<span class="sig-code"><span class="code-num">{code}</span>{_name_s}</span>'
                        + (f'<span class="sig-sector">{_sector_s}</span>' if _sector_s else "")
                        + '</div>'
                        '<div class="sig-row">'
                        f'<span class="k">殖利率</span> <span class="v" style="color:#FFB800;">{cy:.2f}%</span>'
                        '<span class="bar-sep">│</span>'
                        f'<span class="k">5年平均</span> <span class="v" style="color:#22D3EE;">{ay:.2f}%</span>'
                        '<span class="bar-sep">│</span>'
                        f'<span class="k">訊號</span> <span class="v" style="color:#10B981;">近 {lkb} 日觸發 {days_hit} 日</span>'
                        '</div>'
                        '<div class="sig-row">'
                        f'<span class="k">WVF</span> <span class="v">{wvf_val:.2f}</span>'
                        '<span class="bar-sep">│</span>'
                        f'<span class="k">布林上軌</span> <span class="v">{ub_val:.2f}</span>'
                        '<span class="bar-sep">│</span>'
                        f'<span class="k">百分位高點</span> <span class="v">{rh_val:.2f}</span>'
                        '</div>'
                        + ma_row + _inst_row + _verdict_row +
                        '</div>'
                    )
                    st.markdown(_card, unsafe_allow_html=True)

                    if r.get("wvf_data") is not None:
                        with st.expander(f"▸ {code} · {name} — WVF 走勢圖 + 三大法人"):
                            fig = make_wvf_chart(r, name, flow=_flow)
                            st.plotly_chart(fig, use_container_width=True)

            else:
                st.info(f"目前篩選條件下，觀察清單中無股票符合所有 Action Criteria。")

            # Summary table
            with st.expander(f"▸ 完整掃描結果 · {len(no_signal)} 無訊號 / {len(errors)} 無資料"):
                # Collect all SMA periods seen across results
                _all_sma_ps = sorted({
                    p
                    for r in wvf_results
                    for p in r.get("sma_checks", {}).keys()
                })
                rows = []
                for r in wvf_results:
                    row = {
                        "代號": r.get("code", ""),
                        "名稱": r.get("name", ""),
                        "產業別": r.get("sector", ""),
                        "WVF訊號": "🟢 是" if r.get("green") else ("⚠️ 無資料" if "error" in r else "—"),
                        "觸發天數": r.get("days", 0) if "error" not in r else "-",
                        "收盤價": r.get("last_close", "-") if r.get("last_close") else "-",
                        "WVF": r.get("wvf", "-") if "error" not in r else "-",
                    }
                    # Per-SMA columns
                    sma_checks = r.get("sma_checks", {})
                    for p in _all_sma_ps:
                        chk = sma_checks.get(p, {})
                        ab  = chk.get("above")
                        sv  = chk.get("sma")
                        if ab is None:
                            row[f">SMA{p}"] = "—"
                        elif ab:
                            row[f">SMA{p}"] = f"✅ {sv}"
                        else:
                            row[f">SMA{p}"] = f"❌ {sv}"
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ========== 歷史股價驗證工具 ==========
    st.markdown(
        '<div class="section-header">驗證 · 歷史收盤價 · 雙來源交叉比對</div>',
        unsafe_allow_html=True,
    )
    with st.expander("▸ 展開 · 查詢任一股票於指定日期之收盤價（雙來源驗證）"):
        vp_c1, vp_c2, vp_c3 = st.columns([2, 2, 1])
        vp_code = vp_c1.text_input("股票代號 ·", placeholder="例如 6278", key="vp_code")
        vp_date = vp_c2.date_input("查詢日期 ·", value=date.today() - timedelta(days=1), key="vp_date")
        vp_mkt  = vp_c3.selectbox("市場 ·", ["TWSE", "TPEX"], key="vp_mkt")

        if st.button("▶ 執行查詢 · 交叉比對", key="vp_btn"):
            if not vp_code.strip():
                st.warning("請輸入股票代號。")
            else:
                _code = vp_code.strip()
                _results: dict[str, float | None] = {}

                # Source 1: yfinance
                try:
                    from technical import get_historical_prices_batch
                    _yf_p = get_historical_prices_batch([{"code": _code, "market": vp_mkt}], vp_date)
                    _results["yfinance"] = _yf_p.get(_code)
                except Exception as _e:
                    _results["yfinance"] = None

                # Source 2: TWSE/TPEX official daily API
                try:
                    import requests as _req
                    import urllib3; urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    _date_str = vp_date.strftime("%Y%m%d")
                    if vp_mkt == "TWSE":
                        _url = (f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
                                f"?response=json&date={_date_str}&stockNo={_code}")
                        _r = _req.get(_url, timeout=10, verify=False)
                        _j = _r.json()
                        _twse_p = None
                        _twse_actual_date = None
                        if _j.get("stat") == "OK" and _j.get("data"):
                            # rows: [民國日期, 成交股數, 成交金額, 開盤, 最高, 最低, 收盤, 漲跌, 筆數]
                            # Find last trading day on or before vp_date
                            from datetime import datetime as _dt
                            _roc_y = vp_date.year - 1911
                            _target_roc = f"{_roc_y}/{vp_date.strftime('%m/%d')}"
                            _best_row = None
                            for _row in _j["data"]:
                                _d_str = _row[0].strip()  # e.g. "114/04/18"
                                if _d_str <= _target_roc:
                                    _best_row = _row
                                else:
                                    break
                            if _best_row:
                                try:
                                    _twse_p = float(_best_row[6].replace(",", ""))
                                    _twse_actual_date = _best_row[0].strip()
                                except Exception:
                                    pass
                        _results["TWSE官方"] = _twse_p
                        if _twse_actual_date and _twse_actual_date != f"{vp_date.year - 1911}/{vp_date.strftime('%m/%d')}":
                            st.caption(f"ℹ️ {vp_date.strftime('%d.%b.%Y')} 為非交易日，TWSE 使用前一交易日 {_twse_actual_date} 的收盤價。")
                    else:
                        # TPEX: daily close via openapi quotes snapshot — use yfinance only
                        _url = (f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php"
                                f"?l=zh-tw&d={vp_date.year - 1911}/{vp_date.strftime('%m/%d')}&stkno={_code}&o=json")
                        _r = _req.get(_url, timeout=10, verify=False)
                        _j = _r.json()
                        _tpex_p = None
                        if _j.get("iTotalRecords", 0) > 0 and _j.get("aaData"):
                            for _row in _j["aaData"]:
                                # col 0 = date, col 8 = close
                                if len(_row) > 8:
                                    try:
                                        _tpex_p = float(str(_row[8]).replace(",", ""))
                                    except Exception:
                                        pass
                                    break
                        _results["TPEX官方"] = _tpex_p
                except Exception as _e2:
                    _results[f"{'TWSE' if vp_mkt == 'TWSE' else 'TPEX'}官方"] = None

                # Display results
                _date_label_vp = vp_date.strftime("%d.%b.%Y")
            