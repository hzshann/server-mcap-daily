# 每日市值日報

每個工作日早上 8:00 自動寄一封 Email：兩張伺服器產業 + 鴻海集團的 treemap，方塊大小 = 市值、紅漲綠跌。

## 系統架構

```
07:30 Asia/Taipei  →  GitHub Actions
                      ├ 跑 scripts/fetch_and_generate.py
                      ├ yfinance 抓 ~30 家公司
                      ├ 產出 docs/*.html / *.png / *.json
                      └ git commit + push → GitHub Pages 自動部署

08:00 Asia/Taipei  →  n8n Cloud workflow
                      ├ 抓 GitHub Pages 上的 summary.json + preview.png + chart.html
                      └ Gmail node 寄信到 hzshann@gmail.com
```

## 本機操作

```powershell
# 第一次設置
python -m venv .venv
.venv\Scripts\activate
pip install -r scripts\requirements.txt

# 跑一次（產出到 docs/）
python scripts\fetch_and_generate.py

# 看結果
start docs\index.html
```

## 改追蹤公司清單

編輯 `scripts/config.yaml`：

```yaml
groups:
  server:
    title: "伺服器產業"
    base_currency: USD
    companies:
      - { ticker: NVDA, name: NVIDIA, category: 美系芯片 }
      # ...
```

- `ticker`：Yahoo Finance ticker（台股加 `.TW`、港股加 `.HK`、A 股加 `.SS`、日股加 `.T`）
- `base_currency`：圖上市值的比較基準幣別（會自動用 yfinance 抓即時匯率換算）

改完直接 commit + push，GitHub Actions 下次跑就會用新清單。

## GitHub Pages 設定

第一次 push 上去後，到 repo Settings → Pages：
- Source: **Deploy from a branch**
- Branch: **main** / **/docs**

幾分鐘後 `https://<user>.github.io/<repo>/` 就能打開。

## 手動觸發

- **GitHub Actions**：Actions tab → Daily Market Cap Chart → Run workflow
- **n8n**：Editor → Execute Workflow

## 已知限制

- 週末 cron 不跑（`0-4` 是週日~週四 UTC = 週一~週五 Taipei）
- yfinance 偶發抓不到，有 3 次 retry
- Gmail 會 strip JavaScript，所以信件內文用 PNG 預覽，互動式 treemap 以 HTML 附件 + Pages 連結方式提供
- 跨幣別的市值自動轉成 group 的 `base_currency` 比較

## 排錯

| 症狀 | 處理 |
|---|---|
| GitHub Actions 失敗 | Actions tab 看 log；常見是 yfinance rate limit，重跑通常會好 |
| Pages 沒更新 | 檢查最新 commit 是否有改到 `docs/`、Pages 設定 source 是否正確 |
| n8n 抓不到 PNG | 檢查 Pages URL 是否能直接打開 PNG（可能 Pages 還在部署） |
| 中文字變方框 | 本機需要 Microsoft JhengHei；CI 已裝 fonts-noto-cjk |
