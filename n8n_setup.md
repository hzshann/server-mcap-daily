# n8n Cloud workflow 設定指南

## 目標
每工作日 14:45 Asia/Taipei（台股收盤後）從 GitHub Pages 抓圖、組信、寄到 `hzshann@gmail.com`。

## 前置作業
- n8n Cloud 帳號（已有）
- GitHub Pages 已部署：`https://hzshann.github.io/server-mcap-daily/`
- Gmail OAuth credential 在 n8n 已連結（沒有的話照下方說明做）

---

## 步驟 1：連結 Gmail credential（一次性）

1. n8n 左下角 → **Credentials** → **New** → 搜尋 `Gmail OAuth2 API`
2. 照 n8n 畫面指示完成 OAuth：
   - 點 **Sign in with Google**
   - 同意授權
3. 命名 credential 為 `Gmail - hzshann`，存檔

---

## 步驟 2：新建 workflow

1. 點 **Workflows** → **New Workflow** → 命名 `每日市值日報`
2. 依序加 7 個 node（左→右排列）：

### Node 1: Schedule Trigger
- 拉 **Schedule Trigger** 到畫布
- Settings：
  - Trigger Interval: `Custom (Cron)`
  - Cron Expression: `45 14 * * 1-5`
  - Timezone: `Asia/Taipei`

### Node 2-6: HTTP Request × 5

對每個 node：
- 拉 **HTTP Request** node、接在前一個 node 後面
- Method: `GET`
- 設定 URL（見下表）
- **Response 區塊：**
  - JSON 那個：Response Format = `JSON`（預設）
  - PNG 那兩個：Response Format = `File`、Put Output In Field = `data`
  - HTML 那兩個：Response Format = `File`、Put Output In Field = `data`

| Node 名稱（自取） | URL |
|---|---|
| `Get Summary` | `https://hzshann.github.io/server-mcap-daily/summary.json` |
| `Get Server PNG` | `https://hzshann.github.io/server-mcap-daily/server_preview.png` |
| `Get Foxconn PNG` | `https://hzshann.github.io/server-mcap-daily/foxconn_preview.png` |
| `Get Server HTML` | `https://hzshann.github.io/server-mcap-daily/server_chart.html` |
| `Get Foxconn HTML` | `https://hzshann.github.io/server-mcap-daily/foxconn_chart.html` |

> ⚠️ **重要**：每個 HTTP node 在 Options 加 `No Response Body` = false（預設），並務必把前一個 node 的輸出 pass through。最簡單做法是 5 個 HTTP node **串成一條線**（線性），這樣每個 node 都拿得到前面累積的所有 binary data。

### Node 7: Code（組信內容）
- 拉 **Code** node 接在最後一個 HTTP node 後
- Language: `JavaScript`
- 貼下方 JS（見「Code node 程式碼」）

### Node 8: Gmail（寄信）
- 拉 **Gmail** node 接在 Code 後
- Resource: `Message`
- Operation: `Send`
- Credentials: 選剛剛建的 `Gmail - hzshann`
- To: `hzshann@gmail.com`
- Subject: `={{ $json.subject }}`
- Email Type: `HTML`
- Message: `={{ $json.html }}`
- **Add Option** → `Attachments` → 用以下表達式：
  - Attachment Field Name: `server_chart_html,foxconn_chart_html`

---

## Code node 程式碼

把以下整段貼到 Code node 的 Editor：

```javascript
// 取 Summary JSON（在第一個 HTTP node 的輸出）
// n8n 線性串聯後，前面所有 node 的 binary 都會帶到這裡
const items = $input.all();
const summary = $('Get Summary').first().json;

const d = summary.date;
const server = summary.groups.server;
const foxconn = summary.groups.foxconn;

const sign = (pct) => pct >= 0 ? '+' : '';
const arrow = (pct) => pct >= 0 ? '▲' : '▼';

const subject = `每日市值日報 ${d} — 伺服器 ${sign(server.total_change_pct)}${server.total_change_pct.toFixed(2)}% / 鴻海集團 ${sign(foxconn.total_change_pct)}${foxconn.total_change_pct.toFixed(2)}%`;

const renderTopList = (items, color) => items.map(x =>
  `<li>${x.name} (${x.ticker}) <span style="color:${color};font-weight:bold">${sign(x.change_pct)}${x.change_pct.toFixed(2)}%</span></li>`
).join('');

const renderGroupSection = (g, pngCid) => {
  const upColor = '#e63946', downColor = '#00a86b';
  const totalColor = g.total_change_pct >= 0 ? upColor : downColor;
  return `
  <div style="margin:24px 0;padding:20px;background:#fafafa;border-radius:8px;">
    <h2 style="margin:0 0 8px 0;color:#222;">${g.title}</h2>
    <p style="margin:0 0 12px 0;font-size:18px;">
      組合總市值變化：
      <span style="color:${totalColor};font-weight:bold;font-size:22px;">
        ${arrow(g.total_change_pct)} ${Math.abs(g.total_change_pct).toFixed(2)}%
      </span>
    </p>
    <img src="cid:${pngCid}" alt="${g.title} treemap" style="max-width:100%;border-radius:4px;border:1px solid #ddd;">
    <div style="display:flex;gap:20px;margin-top:16px;flex-wrap:wrap;">
      <div style="flex:1;min-width:240px;">
        <h3 style="margin:0 0 6px 0;color:${upColor};">Top 3 漲幅</h3>
        <ul style="margin:0;padding-left:20px;">${renderTopList(g.top_gainers, upColor)}</ul>
      </div>
      <div style="flex:1;min-width:240px;">
        <h3 style="margin:0 0 6px 0;color:${downColor};">Top 3 跌幅</h3>
        <ul style="margin:0;padding-left:20px;">${renderTopList(g.top_losers, downColor)}</ul>
      </div>
    </div>
  </div>`;
};

const html = `<!doctype html>
<html lang="zh-TW">
<head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft JhengHei',sans-serif;max-width:760px;margin:0 auto;padding:20px;background:white;color:#222;">
  <h1 style="border-bottom:3px solid #e63946;padding-bottom:8px;">每日市值日報</h1>
  <p style="color:#666;">資料日期：${d}</p>
  ${renderGroupSection(server, 'server_preview')}
  ${renderGroupSection(foxconn, 'foxconn_preview')}
  <p style="margin-top:32px;text-align:center;">
    <a href="https://hzshann.github.io/server-mcap-daily/"
       style="display:inline-block;padding:10px 20px;background:#0066cc;color:white;text-decoration:none;border-radius:6px;">
      開啟互動式圖表（可 hover 看細節）
    </a>
  </p>
  <p style="color:#999;font-size:12px;text-align:center;margin-top:16px;">
    資料來源：Yahoo Finance | GitHub Actions 每日 07:30 Asia/Taipei 自動更新
  </p>
</body>
</html>`;

// 從前面 HTTP node 拿 binary，重新命名以便 Gmail 引用
const serverPng = $('Get Server PNG').first().binary.data;
const foxconnPng = $('Get Foxconn PNG').first().binary.data;
const serverHtml = $('Get Server HTML').first().binary.data;
const foxconnHtml = $('Get Foxconn HTML').first().binary.data;

return [{
  json: { subject, html },
  binary: {
    server_preview: { ...serverPng, fileName: 'server_preview.png', mimeType: 'image/png' },
    foxconn_preview: { ...foxconnPng, fileName: 'foxconn_preview.png', mimeType: 'image/png' },
    server_chart_html: { ...serverHtml, fileName: `server_chart_${d}.html`, mimeType: 'text/html' },
    foxconn_chart_html: { ...foxconnHtml, fileName: `foxconn_chart_${d}.html`, mimeType: 'text/html' },
  }
}];
```

---

## 步驟 3：測試

1. n8n 右上 **Execute Workflow**
2. 等 ~10 秒看每個 node 是否打勾
3. 打開 Gmail 看信件，預期：
   - Subject 有兩組漲跌幅
   - 上下兩張 treemap 預覽圖
   - Top 3 漲跌清單
   - 兩個 HTML 附件可下載打開互動

## 步驟 4：上線

- workflow 編輯器右上角的 **Active** toggle 切到 ON
- 下個工作日 08:00 會自動跑

---

## 排錯

| 症狀 | 處理 |
|---|---|
| HTTP node 403 | GitHub Pages 還沒部署完成；等 5 分鐘再試 |
| Code node 找不到 binary | 確認 5 個 HTTP node 是線性串聯，且 Response Format = File |
| Gmail node 認證失敗 | 重連 OAuth；Google 可能因為長期沒用 token 過期 |
| 信收到但圖空白 | inline 圖的 `cid:` 名字要跟 binary key 一致（程式裡是 `server_preview` / `foxconn_preview`） |
| 收到信但 subject 出現 undefined | summary.json 結構跟預期不同；先在 n8n 看 Get Summary node 的輸出 |

## 未來擴充
- 加 Slack node 同時推 Slack
- 加 Telegram Bot 同時推手機
- 改 Schedule 為「盤中每 4 小時」（cron `0 9,13,17 * * 1-5`）
