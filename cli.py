"""コマンドラインツール。

  python cli.py demo                 # 架空のデモデータを投入
  python cli.py import posts.txt     # テキスト/CSV/JSON を取り込み（拡張子で判定）
  python cli.py collect              # X / RSS から1回収集
  python cli.py extract [--rules]    # 未処理の投稿を抽出（--rules で LLM を使わない）
  python cli.py reextract [--rules]  # 抽出結果を消して全投稿をやり直す（辞書を更新したとき）
  python cli.py snapshot out.html    # ダッシュボードを1枚の静的 HTML に書き出す
  python cli.py update-site          # 自動更新用: アーカイブ→収集→抽出→site/index.html（GitHub Actions が実行）
  python cli.py reset                # DB を消す
  python cli.py content [--publish]  # 動画・記事・SNS 文・ネタ候補を作る（--publish で設定済みの所へ投稿）
  python cli.py trends               # 伸びている話題を調べて「今日のネタ候補」を表示
  python cli.py youtube-auth         # YouTube のリフレッシュトークンを取得（自分の PC で1回だけ）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import config, pipeline
from app.archetypes import catalog
from app.db import session
from app.sources import demo, manual


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--days", type=int, default=21)
    d.add_argument("--per-day", type=int, default=220)
    i = sub.add_parser("import")
    i.add_argument("path")
    i.add_argument("--author")
    sub.add_parser("collect")
    for name in ("extract", "reextract"):
        e = sub.add_parser(name)
        e.add_argument("--rules", action="store_true")
    sub.add_parser("reset")
    sn = sub.add_parser("snapshot")
    sn.add_argument("out")
    us = sub.add_parser("update-site")
    us.add_argument("--out", default="site/index.html")
    us.add_argument("--keep-days", type=int, default=90)
    us.add_argument("--no-fetch", action="store_true", help="収集せずアーカイブと manual/ だけで作る")
    ct = sub.add_parser("content", help="ショート動画・記事・SNS 投稿・ネタ候補を作る")
    ct.add_argument("--out", default="dist/content")
    ct.add_argument("--publish", action="store_true", help="設定済みの YouTube / SNS / ブログに投稿する")
    ct.add_argument("--kind", choices=["ranking", "trend", "winrate", "matchup", "rank"])
    ct.add_argument("--no-topics", action="store_true", help="話題ネタ（トレンド分析）を行わない")
    ct.add_argument("--topic-videos", type=int, default=int(__import__("os").getenv("SVWB_TOPIC_VIDEOS", "1")))
    ct.add_argument("--force", action="store_true", help="データ不足の日でも作る")
    ct.add_argument("--no-video", action="store_true", help="動画を書き出さない（台本だけ）")
    ct.add_argument("--scale", type=float, default=1.0, help="解像度の倍率（確認用に 0.5 など）")
    sub.add_parser("trends", help="伸びている話題を調べる")
    ya = sub.add_parser("youtube-auth", help="YouTube のリフレッシュトークンを取得する")
    ya.add_argument("--client-id", default=__import__("os").getenv("YT_CLIENT_ID"))
    ya.add_argument("--client-secret", default=__import__("os").getenv("YT_CLIENT_SECRET"))
    a = ap.parse_args()

    if a.cmd == "content":
        from app.content.run import run

        run(Path(a.out), publish=a.publish, kind=a.kind, topics=not a.no_topics,
                  topic_videos=a.topic_videos, force=a.force, make_video=not a.no_video, scale=a.scale)
        print((Path(a.out) / "summary.md").read_text(encoding="utf-8"))
        return

    if a.cmd == "trends":
        from app.content import trends
        from app.content.run import load_history

        ideas, stats = trends.discover(load_history())
        from datetime import date

        print(trends.report_markdown(ideas, stats, date.today().isoformat()))
        return

    if a.cmd == "youtube-auth":
        from app.content import youtube

        if not (a.client_id and a.client_secret):
            sys.exit("--client-id と --client-secret（Google Cloud の OAuth クライアント）を指定してください")
        token = youtube.authorize(a.client_id, a.client_secret)
        print("\nYT_REFRESH_TOKEN に登録する値:\n" + token)
        return

    if a.cmd == "update-site":
        update_site(a.out, a.keep_days, fetch=not a.no_fetch)
        return

    if a.cmd == "snapshot":
        from app.snapshot import build

        html = build()
        Path(a.out).write_text(html, encoding="utf-8")
        print(f"{a.out} に書き出しました（{len(html.encode()) / 1e6:.1f} MB）")
        return

    if a.cmd == "reset":
        for p in config.DATA_DIR.glob(config.DB_PATH.name + "*"):
            p.unlink()
        print("DB を削除しました")
        return

    with session() as c:
        if a.cmd == "demo":
            posts = demo.generate(catalog(), a.days, a.per_day)
            added = pipeline.store_posts(c, posts)
            c.commit()
            stats = pipeline.extract_pending(c, use_llm=False)
            print(f"デモ投稿 {added} 件を追加, 抽出: {stats}")
        elif a.cmd == "import":
            p = Path(a.path)
            blob = p.read_text(encoding="utf-8")
            if p.suffix == ".csv":
                items = manual.from_csv(blob)
            elif p.suffix == ".json":
                items = manual.from_json(blob)
            else:
                items = manual.from_text(blob, a.author)
            added = pipeline.store_posts(c, items)
            c.commit()
            print(f"{added} 件追加, 抽出: {pipeline.extract_pending(c)}")
        elif a.cmd == "collect":
            print(json.dumps(pipeline.collect_once(), ensure_ascii=False))
        elif a.cmd in ("extract", "reextract"):
            if a.cmd == "reextract":
                c.execute("DELETE FROM matches WHERE post_id IN (SELECT id FROM posts WHERE extractor != 'structured')")
                c.execute("DELETE FROM deck_reports")
                c.execute("UPDATE posts SET extracted = 0, extractor = NULL WHERE COALESCE(extractor,'') != 'structured'")
                c.commit()
            print(pipeline.extract_pending(c, use_llm=False if a.rules else None))


def _git_time(path: Path) -> str | None:
    """ファイルを最後にコミットした日時（UTC）。毎回の実行で投稿日時がずれないようにする。"""
    import subprocess
    from datetime import datetime, timezone

    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", str(path)],
                             capture_output=True, text=True, check=True).stdout.strip()
        return datetime.fromisoformat(out).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if out else None
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def update_site(out: str, keep_days: int, fetch: bool = True) -> None:
    """GitHub Actions から毎回呼ばれる処理。毎回まっさらな DB を作り直す。"""
    from app import archive
    from app.snapshot import build

    for p in config.DB_PATH.parent.glob(config.DB_PATH.name + "*"):
        p.unlink()
    stats: dict[str, object] = {}
    with session() as c:
        old = archive.load(config.ARCHIVE_DIR, keep_days)
        known = {(p.source, p.external_id) for p in archive.load(config.ARCHIVE_DIR)}
        stats["archive"] = pipeline.store_posts(c, old)
        # manual/ フォルダ（GitHub の画面から追加できる手動データ）
        manual_posts = []
        if config.MANUAL_DIR.exists():
            for f in sorted(config.MANUAL_DIR.iterdir()):
                if f.name.startswith(("_", ".")) or f.suffix not in (".txt", ".csv", ".json"):
                    continue
                blob = f.read_text(encoding="utf-8")
                manual_posts += (manual.from_csv(blob) if f.suffix == ".csv"
                                 else manual.from_json(blob) if f.suffix == ".json"
                                 else manual.from_text(blob, posted_at=_git_time(f)))
        stats["manual"] = pipeline.store_posts(c, manual_posts)
        if fetch:
            new, fetched = pipeline.fetch_sources(c)
            stats["fetched"] = fetched
            stats["archived"] = archive.append(config.ARCHIVE_DIR, new, known)
            stats["new"] = pipeline.store_posts(c, new)
        c.commit()
        stats["extract"] = pipeline.extract_pending(c)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    page = build(full_document=True, public=True, reload_minutes=10)
    # 記事ページ（広告・アフィリエイト枠付き）と RSS・サイトマップも一緒に公開する
    from app.content import blog

    stats["articles"] = blog.build(Path(out).parent)
    page = _monetize_dashboard(page)
    Path(out).write_text(page, encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


def _monetize_dashboard(page: str) -> str:
    """ダッシュボードに記事一覧へのリンクと（設定があれば）広告枠を足す。"""
    import html

    from app.content import blog, settings

    s = settings()
    nav = ('<nav style="max-width:1200px;margin:8px auto 0;padding:0 16px;font-size:.9rem">'
           '<a href="articles/">📰 毎日の環境まとめ記事</a>'
           + (f' ・ <a href="{html.escape(s["youtube_channel_url"])}" target="_blank" rel="noopener">▶ YouTube</a>'
              if s.get("youtube_channel_url") else "") + "</nav>")
    page = page.replace('<section class="filters"', nav + '\n<section class="filters"', 1)
    extra = blog._ad() + blog._affiliate()
    if extra:
        page = page.replace("</html>", f'<div style="max-width:760px;margin:0 auto;padding:0 16px">{extra}</div>\n</html>', 1)
    if s.get("adsense_client"):
        page = page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
                            + html.escape(s["adsense_client"]) + '" crossorigin="anonymous"></script>', 1)
    return page


if __name__ == "__main__":
    sys.exit(main())
