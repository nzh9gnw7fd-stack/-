"""集計データから収益化用のコンテンツ（ショート動画・記事・SNS 投稿・有料レポート）を自動で作る。

  digest.py   集計結果を1日分の「ネタ」にまとめる（品質ゲート付き）
  writer.py   台本・タイトル・概要欄・SNS 文・記事・週刊レポートを書く（テンプレート＋任意で Claude）
  tts.py      VOICEVOX で読み上げ音声を作る（任意）
  video.py    縦型 1080x1920 のショート動画を描画して mp4 にする（Pillow + ffmpeg）
  youtube.py  YouTube Data API でアップロード
  social.py   Bluesky / Mastodon / X に投稿
  blog.py     記事ページ・一覧・RSS・サイトマップを作る（広告・アフィリエイト枠付き）
  run.py      上をまとめて実行する
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from .. import config


@lru_cache(maxsize=1)
def settings() -> dict:
    path = config.ROOT / "monetize.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def site_url() -> str:
    url = settings().get("site_url") or os.getenv("SVWB_SITE_URL", "")
    if not url and (repo := os.getenv("GITHUB_REPOSITORY")):
        owner, name = repo.split("/", 1)
        url = f"https://{owner.lower()}.github.io/{name}/"
    return url.rstrip("/") + "/" if url else ""


def video_settings() -> dict:
    v = dict(settings().get("video") or {})
    v = {k: val for k, val in v.items() if not k.startswith("_")}
    v["privacy"] = v.get("privacy") or os.getenv("SVWB_YT_PRIVACY") or "private"
    v.setdefault("category_id", "20")
    v.setdefault("min_samples", 30)
    v.setdefault("contains_synthetic_media", False)
    return v
