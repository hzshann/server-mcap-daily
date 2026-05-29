// 貼到 n8n 的 Build Email (Code) node。
// 已改成 base64 data URI 內嵌 PNG，避免 Gmail cid: 不顯示問題。

const summary = $('Get Summary').first().json;
const d = summary.date;
const server = summary.groups.server;
const foxconn = summary.groups.foxconn;

const sign = (pct) => pct >= 0 ? '+' : '';
const arrow = (pct) => pct >= 0 ? '▲' : '▼';

const serverPngB64 = $('Get Server PNG').first().binary.data.data;
const foxconnPngB64 = $('Get Foxconn PNG').first().binary.data.data;
const serverHtmlBin = $('Get Server HTML').first().binary.data;
const foxconnHtmlBin = $('Get Foxconn HTML').first().binary.data;

const subject = `每日市值日報 ${d} — 伺服器 ${sign(server.total_change_pct)}${server.total_change_pct.toFixed(2)}% / 鴻海集團 ${sign(foxconn.total_change_pct)}${foxconn.total_change_pct.toFixed(2)}%`;

const renderTopList = (items, color) => items.map(x =>
  `<li>${x.name} (${x.ticker}) <span style="color:${color};font-weight:bold">${sign(x.change_pct)}${x.change_pct.toFixed(2)}%</span></li>`
).join('');

const renderGroupSection = (g, pngB64) => {
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
    <img src="data:image/png;base64,${pngB64}" alt="${g.title} treemap" style="max-width:100%;border-radius:4px;border:1px solid #ddd;display:block;">
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
  ${renderGroupSection(server, serverPngB64)}
  ${renderGroupSection(foxconn, foxconnPngB64)}
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

return [{
  json: { subject, html },
  binary: {
    server_chart_html: { ...serverHtmlBin, fileName: `server_chart_${d}.html`, mimeType: 'text/html' },
    foxconn_chart_html: { ...foxconnHtmlBin, fileName: `foxconn_chart_${d}.html`, mimeType: 'text/html' }
  }
}];
