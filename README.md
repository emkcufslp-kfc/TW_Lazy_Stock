# 台股股利選股 Dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://tw-lazy-stock.streamlit.app)

## 專案目的

建立一個以股利規則為核心的台股選股 Dashboard，
針對市值前 500 名股票進行篩選，提供互動式查詢介面。

## 篩選規則

1. **連續 10 年配息**：2016–2025 年每年都有發放股利（現金 + 股票）
2. **目前殖利率 ≥ 使用者門檻**：最新年度總股利 / 現價
3. **平均 5 年殖利率 ≥ 使用者門檻**：近 5 年總股利 / 5 / 現價

> ⚠️ 本系統之殖利率 = 現金股利 + 股票股利，與市場常見「現金殖利率」定義不同。

## 功能

- **殖利率篩選** — 連續 10 年配息 + 目前 / 5 年平均殖利率門檻
- **WVF 技術掃描** — Williams VIX Fix 底部訊號，搭配 SMA 10 / 20 / 60 / 200 篩選
- **三大法人動向** — 近 60 日外資 / 投信 / 自營商買賣超（FinMind API）
- **觀察清單** — 儲存最多 20 份 CSV，可重複載入掃描

## 資料來源

| 資料 | 來源 |
|------|------|
| 上市股票清單與價格 | TWSE OpenAPI (`STOCK_DAY_ALL`) |
| 上櫃股票清單與價格 | TPEX OpenAPI (`tpex_mainboard_quotes`) |
| 歷年股利明細 | Goodinfo.tw (`StockDividendPolicy`) |
| WVF / SMA 即時 OHLCV | yfinance |
| 三大法人 | FinMind API（免費，無需 token）|

## 安裝與執行

```bash
# 安裝相依套件
pip install -r requirements.txt

# 建置資料（Goodinfo 爬蟲，約 8 分鐘）
python build_dataset.py

# 或使用 FinMind API（較快，約 3-5 分鐘）
python build_dataset.py --source finmind

# 啟動 Dashboard
streamlit run app.py
```

## 自訂股票數量

```bash
# 取前 500 名市值股票
python build_dataset.py --top 500
```

## Streamlit Cloud 部署

1. Fork 此 repo 至你的 GitHub 帳號
2. 前往 [share.streamlit.io](https://share.streamlit.io) → New app
3. 選擇你的 repo、branch `main`、main file `app.py`
4. 點擊 Deploy — 無需額外設定 Secrets（資料檔已包含在 repo 中）

## 目前狀態 (Current Status)

本專案目前已達 **Production-Ready** 狀態，具備穩定且高效的運作能力。
- **資料管線 (Data Pipeline)**: 已全面採用穩定且防呆的爬蟲機制與備用 API (FinMind) 架構，確保每日台股收盤後資料的精準同步，並支援至全市場 2,000 檔股票的全面掃描。
- **核心算法 (Core Algorithms)**: 實裝機構級別的「5 年平均殖利率」計算模型，結合 Williams VIX Fix (WVF) 底部探測與三大法人動向分析，提供多維度的選股決策支援。
- **系統部署 (Deployment)**: 支援一鍵式 Streamlit Cloud 雲端部署與本地端快速建置，確保開發與線上環境的資料一致性。
- **持續整合 (Continuous Integration)**: 內建資料建置日誌 (`build_log.txt`) 與預載機制，確保 Dashboard 啟動時無需等待，實現零延遲的使用者體驗。

## 專案結構 (Project Structure)

本專案採用模組化架構設計，將資料抓取、業務邏輯、技術指標計算與使用者介面嚴格解耦，確保系統的高可維護性與擴充性：

```text
TW_Lazy_Stock/
├── app.py                    # 應用程式入口：Streamlit 互動式儀表板前端實作
├── build_dataset.py          # 資料建置引擎：負責觸發與協調各資料來源的 ETL 流程
├── screening.py              # 業務邏輯層：實作 10 年連續配息與殖利率篩選核心演算法
├── technical.py              # 量化分析層：WVF 指標運算、移動平均線與三大法人籌碼分析
├── data_sources.py           # 資料訪問層 (Primary)：整合 TWSE/TPEX 與 Goodinfo 爬蟲
├── data_sources_finmind.py   # 資料訪問層 (Fallback)：FinMind API 串接與備援機制
├── utils.py                  # 共用工具函式庫：包含資料清理、快取管理等輔助功能
├── requirements.txt          # 環境依賴清單：詳列專案運行所需之 Python 套件與版本
├── .streamlit/
│   └── config.toml           # 前端配置檔：自訂深色主題與 UI 渲染設定
└── data/                     # 本地資料倉儲 (Local Data Store)
    ├── screened_dataset.csv  # 處理後資料集：已通過初步篩選與清理之基準選股池
    ├── dividend_history.csv  # 歷史股利庫：結構化的 10 年期股利發放明細
    └── build_log.txt         # 系統運行日誌：記錄資料建置狀態、時間戳記與錯誤追蹤
```

## 授權

MIT License
