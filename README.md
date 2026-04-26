# 台股股利選股 Dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://tw-lazy-stock.streamlit.app)

## 專案目的

建立一個以股利規則為核心的台股選股 Dashboard，
針對市值前 300 名股票進行篩選，提供互動式查詢介面。

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

## 專案結構

```
TW_Lazy_Stock/
├── app.py                    # Streamlit Dashboard（主程式）
├── build_dataset.py          # 資料建置腳本
├── data_sources.py           # 資料抓取（TWSE/TPEX/Goodinfo）
├── data_sources_finmind.py   # FinMind API 替代資料來源
├── technical.py              # WVF / SMA 計算 + 三大法人圖表
├── screening.py              # 篩選規則引擎
├── utils.py                  # 工具函式
├── requirements.txt          # Python 相依套件
├── .streamlit/
│   └── config.toml           # 深色主題設定
└── data/
    ├── screened_dataset.csv       # 篩選結果（預建）
    ├── dividend_history.csv       # 股利明細（預建）
    └── build_log.txt              # 建置日誌
```

## 授權

MIT License
