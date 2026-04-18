# 台股股利選股 Dashboard

## 專案目的

建立一個以股利規則為核心的台股選股 Dashboard，
針對市值前 300 名股票進行篩選，提供互動式查詢介面。

## 篩選規則

1. **連續 10 年配息**：2016–2025 年每年都有發放股利（現金 + 股票）
2. **目前殖利率 ≥ 使用者門檻**：最新年度總股利 / 現價
3. **平均 5 年殖利率 ≥ 使用者門檻**：近 5 年總股利 / 5 / 現價

> ⚠️ 本系統之殖利率 = 現金股利 + 股票股利，與市場常見「現金殖利率」定義不同。

## 資料來源

| 資料 | 來源 |
|------|------|
| 上市股票清單與價格 | TWSE OpenAPI (`STOCK_DAY_ALL`) |
| 上櫃股票清單與價格 | TPEX OpenAPI (`tpex_mainboard_quotes`) |
| 歷年股利明細 | Goodinfo.tw (`StockDividendPolicy`) |

## 安裝與執行

```bash
# 安裝相依套件
pip install -r requirements.txt

# 建置資料（約需 8 分鐘）
python build_dataset.py

# 啟動 Dashboard
streamlit run app.py
```

## 自訂股票數量

```bash
# 取前 500 名市值股票
python build_dataset.py --top 500
```

## 專案結構

```
tw-dividend-dashboard/
├── app.py                # Streamlit Dashboard
├── build_dataset.py      # 資料建置腳本
├── data_sources.py       # 資料抓取（TWSE/TPEX/Goodinfo）
├── screening.py          # 篩選規則引擎
├── utils.py              # 工具函式
├── requirements.txt      # Python 相依套件
├── .gitignore
├── .streamlit/
│   └── config.toml       # 深色主題設定
└── data/
    ├── screened_dataset.csv   # 篩選結果
    ├── dividend_history.csv   # 股利明細
    └── build_log.txt          # 建置日誌
```

## 授權

MIT License
