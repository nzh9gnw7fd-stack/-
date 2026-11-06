"""コマンドラインツール。

  python cli.py demo                 # 架空のデモデータを投入
  python cli.py import posts.txt     # テキスト/CSV/JSON を取り込み（拡張子で判定）
  python cli.py collect              # X / RSS から1回収集
  python cli.py extract [--rules]    # 未処理の投稿を抽出（--rules で LLM を使わない）
  python cli.py reextract [--rules]  # 抽出結果を消して全投稿をやり直す（辞書を更新したとき）
  python cli.py reset                # DB を消す
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
    a = ap.parse_args()

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


if __name__ == "__main__":
    sys.exit(main())
