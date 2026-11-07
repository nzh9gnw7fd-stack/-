"""使い方:

  python -m note_auto login                 # 初回だけ。ブラウザで note にログインして状態を保存
  python -m note_auto generate [-n 3]       # 未着手のテーマから記事を書いて採点（out/<ID>/ に保存）
  python -m note_auto list                  # 生成済み記事の状態
  python -m note_auto approve <ID>          # needs_review の記事を手で直したあと承認する
  python -m note_auto post [<ID>] [--publish]  # 承認済みの記事を note へ（既定は下書き保存）
  python -m note_auto run [--publish]       # generate 1件 → 合格なら post（定期実行用）
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import config, store


def _post_one(topic_id: str, publish: bool) -> bool:
    from .publisher import PublishError, post

    if publish and store.posts_today() >= config.DAILY_LIMIT:
        print(f"今日の公開上限（{config.DAILY_LIMIT}件）に達したので止めます。NOTE_DAILY_LIMIT で変更できます")
        return False
    a = store.load_article(topic_id)
    if a.status not in ("approved", "drafted"):
        print(f"{topic_id}: status={a.status} なので投稿しません（承認するには approve）")
        return False
    try:
        url = post(a, publish=publish)
    except PublishError as e:
        print(f"{topic_id}: 投稿に失敗: {e}")
        return False
    store.record_post(a, url, published=publish)
    print(f"{topic_id}: {'公開しました' if publish else '下書き保存しました'} {url}")
    if publish:
        print(f"  告知文: {a.promo_post}\n  {url}")
    return True


def cmd_generate(n: int, topic_id: str | None) -> list[str]:
    from .generate import create

    topics = store.load_topics()
    if topic_id:
        targets = [t for t in topics if t.id == topic_id]
        if not targets:
            sys.exit(f"テーマ {topic_id} が topics.json にありません")
    else:
        targets = store.pending_topics(topics)[:n]
    if not targets:
        print("未着手のテーマがありません。topics.json に追加してください")
    done = []
    for t in targets:
        print(f"{t.id}: 執筆中…（{t.theme}）")
        a = create(t)
        path = store.save_article(a)
        r = a.review
        print(f"  → {a.status}  score={r.get('score')} safe={r.get('safe')}  「{a.title}」 {a.price}円")
        for issue in r.get("issues", [])[:5]:
            print(f"     - {issue}")
        print(f"  保存先: {path.parent}")
        done.append(t.id)
    return done


def cmd_list() -> None:
    state = store.load_state()
    if not state["articles"]:
        print("まだ記事がありません")
    for k, v in state["articles"].items():
        print(f"{k:20} {v.get('status', ''):13} {str(v.get('score', '')):>4}  {v.get('title', '')}  {v.get('url', '')}")
    print(f"今日の公開数: {store.posts_today()} / {config.DAILY_LIMIT}")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="python -m note_auto", description="note 有料記事の自動執筆・投稿")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    g = sub.add_parser("generate")
    g.add_argument("-n", type=int, default=1)
    g.add_argument("--topic")
    sub.add_parser("list")
    a = sub.add_parser("approve")
    a.add_argument("topic")
    p = sub.add_parser("post")
    p.add_argument("topic", nargs="?")
    p.add_argument("--publish", action="store_true", help="下書きではなく有料記事として公開する")
    r = sub.add_parser("run")
    r.add_argument("--publish", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "login":
        from .publisher import login

        print(f"保存しました: {login()}（このファイルは他人に渡さないでください）")
    elif args.cmd == "generate":
        cmd_generate(args.n, args.topic)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "approve":
        store.set_status(args.topic, "approved")
        print(f"{args.topic} を承認しました")
    elif args.cmd == "post":
        ids = [args.topic] if args.topic else store.articles_with_status("approved")[:1]
        if not ids:
            print("承認済み（approved）の記事がありません")
        for i in ids:
            _post_one(i, args.publish)
    elif args.cmd == "run":
        if args.publish and store.posts_today() >= config.DAILY_LIMIT:
            print("今日の公開上限に達しています")
            return
        # 前回の承認済みが残っていればそれを先に出す
        ids = store.articles_with_status("approved")[:1] or cmd_generate(1, None)
        for i in ids:
            if store.load_article(i).status == "approved":
                _post_one(i, args.publish)
            else:
                print(f"{i}: 品質チェック不合格のため投稿しません。out/{i}/preview.md を確認して直し、approve してください")


if __name__ == "__main__":
    main()
