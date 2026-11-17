"""記事ページ・一覧・RSS・サイトマップを作る（GitHub Pages に一緒に載せる）。

記事の中身は content/articles/*.json に保存しておき（Actions がコミット）、
サイトを作るたびに monetize.json の広告・アフィリエイト設定を差し込んで HTML にする。
こうしておくと、あとから AdSense に合格したときに過去記事すべてに広告が入る。
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import config
from . import settings, site_url

ARTICLES_DIR = config.ROOT / "content" / "articles"
JST = timezone(timedelta(hours=9))
CSS = """
:root{color-scheme:light;--bg:#f4f4f2;--card:#fcfcfb;--text:#0b0b0b;--sub:#52514e;--muted:#7a7974;--line:#e2e1dc;--accent:#2a78d6;--bar:#e8e7e3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#111110;--card:#1a1a19;--text:#f0efec;--sub:#c3c2b7;--muted:#8e8d86;--line:#2c2c2a;--accent:#3987e5;--bar:#2a2a28}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#111110;--card:#1a1a19;--text:#f0efec;--sub:#c3c2b7;--muted:#8e8d86;--line:#2c2c2a;--accent:#3987e5;--bar:#2a2a28}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.8 "Zen Kaku Gothic New",system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}a{color:var(--accent)}
header.site{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line);background:var(--card)}
header.site a{text-decoration:none;font-weight:700;color:var(--text)}
h1{font-size:1.5rem;line-height:1.4;margin:.4em 0}h2{font-size:1.15rem;margin:2em 0 .6em;padding-left:10px;border-left:4px solid var(--accent)}
.meta{color:var(--muted);font-size:.85rem}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0}
table{width:100%;border-collapse:collapse;font-size:.92rem;display:block;overflow-x:auto}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.bar{display:grid;grid-template-columns:minmax(7em,40%) 1fr 4.5em;gap:8px;align-items:center;margin:6px 0;font-size:.92rem}
.bar i{display:block;height:12px;border-radius:6px;background:var(--bar)}.bar i b{display:block;height:100%;border-radius:6px}
.pr{font-size:.8rem;color:var(--muted)}.pr b{border:1px solid var(--muted);border-radius:4px;padding:0 4px;margin-right:6px}
.ad{margin:24px 0;min-height:100px}.yt{position:relative;padding-top:177%;max-width:360px}.yt iframe{position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:12px}
ul.list{list-style:none;padding:0}ul.list li{padding:12px 0;border-bottom:1px solid var(--line)}
footer{color:var(--muted);font-size:.8rem;margin-top:48px}
"""


def save(article: dict) -> Path:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    p = ARTICLES_DIR / f"{article['slug']}.json"
    p.write_text(json.dumps(article, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def load_all() -> list[dict]:
    out = []
    for p in sorted(ARTICLES_DIR.glob("*.json"), reverse=True) if ARTICLES_DIR.exists() else []:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return out


e = html.escape


def _ad() -> str:
    s = settings()
    if not s.get("adsense_client"):
        return ""
    slot = f' data-ad-slot="{e(s["adsense_slot"])}"' if s.get("adsense_slot") else ""
    return (f'<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="{e(s["adsense_client"])}"'
            f'{slot} data-ad-format="auto" data-full-width-responsive="true"></ins>'
            "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>")


def _affiliate() -> str:
    s = settings()
    items = [a for a in s.get("affiliate") or [] if a.get("url")]
    sup = [a for a in s.get("support_links") or [] if a.get("url")]
    out = ""
    if items:
        lis = "".join(f'<li><a href="{e(a["url"])}" rel="sponsored noopener" target="_blank">{e(a["label"])}</a>'
                      f'{"　" + e(a["note"]) if a.get("note") else ""}</li>' for a in items)
        out += f'<div class="card"><p class="pr"><b>PR</b>この枠には広告（アフィリエイトリンク）を含みます</p><ul>{lis}</ul>'
        if s.get("amazon_associate"):
            out += '<p class="pr">Amazonのアソシエイトとして、当サイトは適格販売により収入を得ています。</p>'
        out += "</div>"
    if sup:
        out += '<div class="card"><b>もっと詳しく</b><ul>' + "".join(
            f'<li><a href="{e(a["url"])}" target="_blank" rel="noopener">{e(a["label"])}</a></li>' for a in sup) + "</ul></div>"
    return out


def _block(b: dict) -> str:
    if "h2" in b:
        return f"<h2>{e(b['h2'])}</h2>"
    if "p" in b:
        return f"<p>{e(b['p'])}</p>"
    if "ul" in b:
        return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in b["ul"]) + "</ul>"
    if "bars" in b:
        top = max((v for _, v, _, _ in b["bars"]), default=1) or 1
        return '<div class="card">' + "".join(
            f'<div class="bar"><span>{e(lbl)}</span><i><b style="width:{v / top * 100:.1f}%;background:{e(c)}"></b></i>'
            f"<span>{e(txt)}</span></div>" for lbl, v, txt, c in b["bars"]) + "</div>"
    if "table" in b:
        t = b["table"]
        return ("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in t["head"]) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in t["rows"])
                + "</tbody></table>")
    if "youtube" in b:
        vid = b["youtube"].rstrip("/").rsplit("/", 1)[-1].split("=")[-1]
        return (f'<div class="yt"><iframe src="https://www.youtube-nocookie.com/embed/{e(vid)}" title="動画" '
                'allowfullscreen loading="lazy"></iframe></div>')
    return ""


def _page(title: str, body: str, desc: str = "", canonical: str = "") -> str:
    s = settings()
    brand = s.get("brand", "")
    ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
           f'{e(s["adsense_client"])}" crossorigin="anonymous"></script>') if s.get("adsense_client") else ""
    can = f'<link rel="canonical" href="{e(canonical)}">' if canonical else ""
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">{can}
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="article">
<link rel="alternate" type="application/rss+xml" title="{e(brand)}" href="../feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;700&display=swap">
{ads}<style>{CSS}</style></head><body>
<header class="site"><a href="../">{e(brand)}</a><a href="./">記事一覧</a></header>
<main>{body}<footer>数値は SNS の公開投稿から自動で推定したもので、公式の統計ではありません。<br>
<a href="../">ダッシュボード</a> ・ <a href="../feed.xml">RSS</a></footer></main></body></html>
"""


def build(site_dir: Path) -> int:
    """site_dir/articles/ 以下を作り直す。記事数を返す。"""
    arts = load_all()
    out = site_dir / "articles"
    out.mkdir(parents=True, exist_ok=True)
    base = site_url()
    for a in arts:
        body = (f"<article><p class=\"meta\">{e(a['date'])}</p><h1>{e(a['title'])}</h1>{_ad()}"
                + "".join(_block(b) for b in a["blocks"][:6]) + _ad()
                + "".join(_block(b) for b in a["blocks"][6:]) + _affiliate() + "</article>")
        (out / f"{a['slug']}.html").write_text(
            _page(a["title"], body, a.get("summary", ""), f"{base}articles/{a['slug']}.html" if base else ""), encoding="utf-8")
    items = "".join(f'<li><a href="{e(a["slug"])}.html">{e(a["title"])}</a><div class="meta">{e(a["date"])}　'
                    f'{e(a.get("summary", ""))}</div></li>' for a in arts)
    (out / "index.html").write_text(_page(f"環境まとめ記事一覧｜{settings().get('brand', '')}",
                                          f"<h1>環境まとめ記事</h1>{_ad()}<ul class=\"list\">{items or '<li>まだ記事はありません</li>'}</ul>",
                                          "毎日自動更新の環境まとめ記事"), encoding="utf-8")
    _feed(site_dir, arts[:30], base)
    _sitemap(site_dir, arts, base)
    s = settings()
    if s.get("adsense_client"):
        pub = s["adsense_client"].removeprefix("ca-")
        (site_dir / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    (site_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n" + (f"Sitemap: {base}sitemap.xml\n" if base else ""),
                                         encoding="utf-8")
    return len(arts)


def _feed(site_dir: Path, arts: list[dict], base: str) -> None:
    def rfc822(d: str) -> str:
        return datetime.strptime(d, "%Y-%m-%d").replace(hour=19, tzinfo=JST).strftime("%a, %d %b %Y %H:%M:%S %z")

    items = "".join(f"<item><title>{e(a['title'])}</title><link>{e(base)}articles/{e(a['slug'])}.html</link>"
                    f"<guid>{e(base)}articles/{e(a['slug'])}.html</guid><pubDate>{rfc822(a['date'])}</pubDate>"
                    f"<description>{e(a.get('summary', ''))}</description></item>" for a in arts)
    (site_dir / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{e(settings().get("brand", ""))}</title>'
        f"<link>{e(base)}</link><description>環境まとめ記事</description><language>ja</language>{items}</channel></rss>",
        encoding="utf-8")


def _sitemap(site_dir: Path, arts: list[dict], base: str) -> None:
    if not base:
        return
    urls = [base, f"{base}articles/"] + [f"{base}articles/{a['slug']}.html" for a in arts]
    (site_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{e(u)}</loc></url>" for u in urls) + "</urlset>", encoding="utf-8")
