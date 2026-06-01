# -*- coding: utf-8 -*-
"""
每日市值日報 — 抓 yfinance、產出 treemap HTML/PNG/JSON
本機跑：  python scripts/fetch_and_generate.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import yaml
import yfinance as yf

# Windows console UTF-8 fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "scripts" / "config.yaml"
OUTPUT_DIR = ROOT / "docs"
OUTPUT_DIR.mkdir(exist_ok=True)

# 顏色：漲紅、跌綠、平盤灰（台股慣例）
COLOR_UP = "#e63946"
COLOR_DOWN = "#00a86b"
COLOR_FLAT = "#dddddd"

# 漲跌幅顏色映射範圍：±3% 為飽和上下限
COLOR_RANGE_PCT = 3.0

# Plotly 字型 fallback chain：Linux 走 Noto CJK（apt fonts-noto-cjk）、Windows 走 Microsoft JhengHei
PLOTLY_FONT_FAMILY = "Noto Sans CJK TC, Noto Sans CJK SC, Microsoft JhengHei, PingFang TC, sans-serif"



def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fetch_one(ticker: str, retries: int = 3) -> Optional[dict]:
    """抓單一 ticker 的 last_close / prev_close / market_cap / currency"""
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", auto_adjust=False)
            if hist.empty or len(hist) < 2:
                print(f"  ⚠️  {ticker} history 資料不足", file=sys.stderr)
                return None
            last_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            info = t.info or {}
            shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            market_cap = info.get("marketCap")
            if not market_cap and shares:
                market_cap = float(shares) * last_close
            currency = info.get("currency") or "USD"
            return {
                "ticker": ticker,
                "last_close": last_close,
                "prev_close": prev_close,
                "change_pct": (last_close - prev_close) / prev_close * 100,
                "market_cap_native": float(market_cap) if market_cap else 0.0,
                "currency": currency,
                "as_of": hist.index[-1].strftime("%Y-%m-%d"),
            }
        except Exception as e:
            print(f"  ⚠️  {ticker} attempt {attempt + 1} failed: {e}", file=sys.stderr)
            time.sleep(2)
    return None


_fx_cache: Dict[str, float] = {}


def get_fx_rate(from_ccy: str, to_ccy: str) -> float:
    """取得即時匯率，例如 USD → TWD"""
    if from_ccy == to_ccy:
        return 1.0
    key = f"{from_ccy}{to_ccy}"
    if key in _fx_cache:
        return _fx_cache[key]
    # yfinance FX ticker 格式：USDTWD=X
    pair = f"{from_ccy}{to_ccy}=X"
    try:
        hist = yf.Ticker(pair).history(period="5d", auto_adjust=False)
        if not hist.empty:
            rate = float(hist["Close"].iloc[-1])
            _fx_cache[key] = rate
            return rate
    except Exception as e:
        print(f"  ⚠️  匯率 {pair} 抓不到：{e}", file=sys.stderr)
    # Fallback：嘗試反向 + 取倒數
    inv = f"{to_ccy}{from_ccy}=X"
    try:
        hist = yf.Ticker(inv).history(period="5d", auto_adjust=False)
        if not hist.empty:
            rate = 1.0 / float(hist["Close"].iloc[-1])
            _fx_cache[key] = rate
            return rate
    except Exception:
        pass
    print(f"  ⚠️  匯率 {from_ccy}→{to_ccy} 失敗，用 1.0 替代", file=sys.stderr)
    return 1.0


def fetch_group(group_cfg: dict) -> List[dict]:
    companies = group_cfg["companies"]
    base_ccy = group_cfg.get("base_currency", "USD")
    rows = []
    for c in companies:
        print(f"  抓 {c['ticker']} ({c['name']}) ...")
        data = _fetch_one(c["ticker"])
        if not data:
            continue
        # 匯率轉換成 base currency
        rate = get_fx_rate(data["currency"], base_ccy)
        data["market_cap_base"] = data["market_cap_native"] * rate
        data["base_currency"] = base_ccy
        data["name"] = c["name"]
        data["category"] = c["category"]
        rows.append(data)
    return rows


def _color_for_pct(pct: float) -> str:
    """漲跌幅 → 顏色（紅漲綠跌，飽和度依絕對值）"""
    if pct == 0:
        return COLOR_FLAT
    intensity = min(abs(pct) / COLOR_RANGE_PCT, 1.0)
    if pct > 0:
        # COLOR_FLAT (dddddd) → COLOR_UP (e63946)
        r1, g1, b1 = 0xdd, 0xdd, 0xdd
        r2, g2, b2 = 0xe6, 0x39, 0x46
    else:
        r1, g1, b1 = 0xdd, 0xdd, 0xdd
        r2, g2, b2 = 0x00, 0xa8, 0x6b
    r = int(r1 + (r2 - r1) * intensity)
    g = int(g1 + (g2 - g1) * intensity)
    b = int(b1 + (b2 - b1) * intensity)
    return f"#{r:02x}{g:02x}{b:02x}"


def _fmt_mcap(value_base: float, base_ccy: str) -> str:
    if base_ccy == "USD":
        if value_base >= 1e12:
            return f"${value_base / 1e12:.2f}T"
        if value_base >= 1e9:
            return f"${value_base / 1e9:.1f}B"
        return f"${value_base / 1e6:.0f}M"
    # TWD
    if value_base >= 1e12:
        return f"{value_base / 1e12:.2f}兆"
    if value_base >= 1e8:
        return f"{value_base / 1e8:.0f}億"
    return f"{value_base / 1e6:.0f}M"


def _fmt_price(price: float, currency: str) -> str:
    """收盤股價格式：含幣別符號"""
    symbols = {"USD": "$", "TWD": "NT$", "HKD": "HK$", "JPY": "¥", "CNY": "¥"}
    sym = symbols.get(currency, f"{currency} ")
    if currency == "JPY":
        return f"{sym}{price:,.0f}"
    return f"{sym}{price:,.2f}"


def build_treemap_figure(rows: List[dict], title: str, base_ccy: str) -> go.Figure:
    """同一張 Plotly Figure，輸出互動式 HTML 與靜態 PNG（kaleido）共用"""
    rows_sorted = sorted(rows, key=lambda r: r["market_cap_base"], reverse=True)
    labels = [r["name"] for r in rows_sorted]
    values = [r["market_cap_base"] for r in rows_sorted]
    colors = [_color_for_pct(r["change_pct"]) for r in rows_sorted]
    customdata = [
        [
            r["ticker"],
            r["category"],
            r["change_pct"],
            _fmt_mcap(r["market_cap_base"], base_ccy),
            r["as_of"],
            _fmt_price(r["last_close"], r["currency"]),
        ]
        for r in rows_sorted
    ]
    text = [
        f"<b>{r['name']}</b><br>{r['change_pct']:+.2f}%<br>{_fmt_price(r['last_close'], r['currency'])}<br>{_fmt_mcap(r['market_cap_base'], base_ccy)}"
        for r in rows_sorted
    ]
    fig = go.Figure(
        go.Treemap(
            labels=labels,
            parents=[""] * len(rows_sorted),
            values=values,
            text=text,
            textinfo="text",
            customdata=customdata,
            hovertemplate=(
                "<b>%{label}</b> (%{customdata[0]})<br>"
                "分類：%{customdata[1]}<br>"
                "漲跌：%{customdata[2]:+.2f}%<br>"
                "收盤：%{customdata[5]}<br>"
                "市值：%{customdata[3]}<br>"
                "資料日：%{customdata[4]}<extra></extra>"
            ),
            marker=dict(colors=colors, line=dict(width=2, color="white")),
            textfont=dict(size=16, color="white", family=PLOTLY_FONT_FAMILY),
            tiling=dict(packing="squarify"),
        )
    )
    today = datetime.now().strftime("%Y-%m-%d")
    fig.update_layout(
        title=dict(text=f"{title}（{today}）", font=dict(size=22, family=PLOTLY_FONT_FAMILY)),
        font=dict(family=PLOTLY_FONT_FAMILY),
        margin=dict(t=60, l=10, r=10, b=10),
        paper_bgcolor="#fafafa",
        # 'show' = 全部 tile 都要顯示文字、自動縮小到能塞下；minsize=6 給一個很低的下限
        uniformtext=dict(minsize=6, mode="show"),
    )
    return fig


def build_summary(rows: List[dict], group_key: str, group_cfg: dict) -> dict:
    base_ccy = group_cfg.get("base_currency", "USD")
    today = datetime.now().strftime("%Y-%m-%d")
    total_mcap = sum(r["market_cap_base"] for r in rows)
    prev_total = sum(r["market_cap_base"] * (r["prev_close"] / r["last_close"]) for r in rows if r["last_close"] > 0)
    total_change = (total_mcap - prev_total) / prev_total * 100 if prev_total > 0 else 0
    sorted_by_pct = sorted(rows, key=lambda r: r["change_pct"], reverse=True)
    return {
        "date": today,
        "group": group_key,
        "title": group_cfg["title"],
        "base_currency": base_ccy,
        "total_market_cap": total_mcap,
        "total_change_pct": total_change,
        "top_gainers": [
            {
                "name": r["name"],
                "ticker": r["ticker"],
                "change_pct": r["change_pct"],
                "last_close": r["last_close"],
                "currency": r["currency"],
                "price_display": _fmt_price(r["last_close"], r["currency"]),
            }
            for r in sorted_by_pct[:3]
        ],
        "top_losers": [
            {
                "name": r["name"],
                "ticker": r["ticker"],
                "change_pct": r["change_pct"],
                "last_close": r["last_close"],
                "currency": r["currency"],
                "price_display": _fmt_price(r["last_close"], r["currency"]),
            }
            for r in sorted_by_pct[-3:][::-1]
        ],
        "all": [
            {
                "name": r["name"],
                "ticker": r["ticker"],
                "category": r["category"],
                "change_pct": r["change_pct"],
                "last_close": r["last_close"],
                "currency": r["currency"],
                "price_display": _fmt_price(r["last_close"], r["currency"]),
                "market_cap": r["market_cap_base"],
            }
            for r in sorted(rows, key=lambda r: r["market_cap_base"], reverse=True)
        ],
    }


def write_index_html(group_summaries: Dict[str, dict]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    cards = []
    for key, s in group_summaries.items():
        sign = "▲" if s["total_change_pct"] >= 0 else "▼"
        color = COLOR_UP if s["total_change_pct"] >= 0 else COLOR_DOWN
        cards.append(
            f"""
            <a class="card" href="{key}_chart.html">
              <h2>{s['title']}</h2>
              <p class="change" style="color:{color}">{sign} {abs(s['total_change_pct']):.2f}%</p>
              <p class="hint">點此查看互動式圖表 →</p>
            </a>"""
        )
    html = f"""<!doctype html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8">
  <title>每日市值日報 {today}</title>
  <style>
    body {{ font-family: "Microsoft JhengHei", "Noto Sans CJK TC", sans-serif; background:#f5f5f5; margin:0; padding:40px; }}
    h1 {{ color:#333; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:20px; margin-top:20px; }}
    .card {{ background:white; padding:24px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.08); text-decoration:none; color:#222; transition:transform .15s; }}
    .card:hover {{ transform:translateY(-2px); }}
    .change {{ font-size:32px; font-weight:bold; margin:8px 0; }}
    .hint {{ color:#888; font-size:13px; margin:0; }}
    footer {{ margin-top:30px; color:#999; font-size:12px; }}
  </style>
</head>
<body>
  <h1>每日市值日報</h1>
  <p>資料日期：{today}</p>
  <div class="cards">{''.join(cards)}</div>
  <footer>資料來源：Yahoo Finance（yfinance）| 自動更新：每工作日 07:30 Asia/Taipei</footer>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")


def main():
    print("讀取設定...")
    cfg = load_config()
    summaries = {}
    for group_key, group_cfg in cfg["groups"].items():
        print(f"\n=== 處理 {group_key}：{group_cfg['title']} ===")
        rows = fetch_group(group_cfg)
        if not rows:
            print(f"  ❌ {group_key} 沒有資料，跳過")
            continue
        base_ccy = group_cfg.get("base_currency", "USD")
        title = group_cfg["title"]

        fig = build_treemap_figure(rows, title, base_ccy)

        # 互動式 HTML（給 GitHub Pages + email 附件）
        html_path = OUTPUT_DIR / f"{group_key}_chart.html"
        html_path.write_text(
            fig.to_html(include_plotlyjs="cdn", full_html=True), encoding="utf-8"
        )
        print(f"  ✓ {group_key}_chart.html")

        # 靜態 PNG（給 email inline 顯示，透過 kaleido 直接從 Plotly figure 轉）
        png_path = OUTPUT_DIR / f"{group_key}_preview.png"
        fig.write_image(str(png_path), format="png", width=1400, height=900, scale=1.5)
        print(f"  ✓ {group_key}_preview.png")

        summary = build_summary(rows, group_key, group_cfg)
        (OUTPUT_DIR / f"{group_key}_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summaries[group_key] = summary
        print(f"  ✓ {group_key}_summary.json")

    combined = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "groups": summaries,
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✓ summary.json（彙整）")

    write_index_html(summaries)
    print("✓ index.html")
    print(f"\n全部完成 — 檔案在 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
