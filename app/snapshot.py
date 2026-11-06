"""ダッシュボードを1枚の静的 HTML に書き出す（サーバーなしで共有・閲覧するため）。

API の応答をフィルタの組み合わせごとに事前計算して埋め込み、fetch を差し替えて返す。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from . import config
from .archetypes import catalog
from .main import app

logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

FORMATS = ["rotation", "unlimited"]
DAYS = [7, 14, 30]
CHART_JS = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"
JST = timezone(timedelta(hours=9))


def _key(path: str, params: dict) -> str:
    items = sorted((k, str(v)) for k, v in params.items() if v not in (None, ""))
    return path + ("?" + urlencode(items) if items else "")


def build(title: str = "SVWB メタトラッカー", full_document: bool = False, public: bool = False,
          reload_minutes: int = 0) -> str:
    """full_document=True で <!doctype html> 付きの単体ページ（GitHub Pages 用）を返す。
    public=True のとき投稿本文は先頭だけにして元投稿へのリンクを付ける（全文の転載を避ける）。
    reload_minutes>0 のとき、開いたままのページを定期的に再読み込みして最新版を表示する。"""
    client = TestClient(app)
    cat = catalog()
    data: dict[str, object] = {}

    def grab(path: str, **params):
        r = client.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        data[_key(path, params)] = r.json()

    meta = client.get("/api/meta").json()
    # スナップショットでは自動収集・抽出の状態は意味がないので固定表示
    if not public:
        meta["sources"] = {"x": False, "rss": 0, "social": False, "llm": False}
    data["/api/meta"] = meta
    for fmt in FORMATS:
        for days in DAYS:
            grab("/api/ranks", format=fmt, days=days)
            for rank in [None, *cat.ranks]:
                for path in ("/api/summary", "/api/decks", "/api/shares"):
                    grab(path, format=fmt, days=days, ranks=rank)
                grab("/api/matchups", format=fmt, days=days, ranks=rank, top=10)
    grab("/api/posts", limit=60)
    for name in cat.archetype_names():
        grab("/api/posts", limit=60, deck=name)
    if public:
        for k, v in data.items():
            if k.startswith("/api/posts"):
                for p in v:
                    if len(p["text"]) > 90:
                        p["text"] = p["text"][:90] + "…"

    html = (config.ROOT / "static" / "index.html").read_text(encoding="utf-8")
    css = (config.ROOT / "static" / "style.css").read_text(encoding="utf-8")
    js = (config.ROOT / "static" / "app.js").read_text(encoding="utf-8")

    head_links = "\n".join(re.findall(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts[^>]+>', html))
    body = html.split("<body>", 1)[1].split("</body>", 1)[0]
    body = re.sub(r'<script src="/static/app.js"></script>', "", body)
    # 期間の選択肢を埋め込み済みのものに絞る
    body = re.sub(
        r'<select id="fDays">.*?</select>',
        '<select id="fDays">' + "".join(
            f'<option value="{d}"{" selected" if d == 14 else ""}>{d}日</option>' for d in DAYS
        ) + "</select>",
        body,
        flags=re.S,
    )
    generated = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    shim = f"""
window.SVWB_SNAPSHOT = {{ generated: {json.dumps(generated)}, reloadMinutes: {int(reload_minutes)} }};
(function () {{
  const DATA = {payload};
  const norm = (u) => {{
    const url = new URL(u, "https://snapshot.local");
    const p = [...url.searchParams.entries()].filter(([, v]) => v !== "").sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
    return url.pathname + (p.length ? "?" + new URLSearchParams(p).toString() : "");
  }};
  window.fetch = async (u, opts) => {{
    const k = norm(String(u));
    if (opts && opts.method && opts.method !== "GET") return new Response(JSON.stringify({{ detail: "スナップショットでは使えません" }}), {{ status: 400 }});
    const hit = DATA[k];
    return new Response(JSON.stringify(hit === undefined ? [] : hit), {{ status: hit === undefined ? 404 : 200, headers: {{ "Content-Type": "application/json" }} }});
  }};
}})();
"""
    page = f"""<title>{title}</title>
<meta name="claude:viewport-fit-sides" content="cover">
{head_links}
<style>
{css}
</style>
<script src="{CHART_JS}"></script>
{body}
<script>{shim}</script>
<script>
{js}
</script>
"""
    if full_document:
        page = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="シャドバWBのデッキ使用率・推定勝率・相性・ランク帯別分布を、SNS の公開投稿から自動で推定して表示します。">
{page}
</html>
"""
    return page
