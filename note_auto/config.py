from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 執筆とチェックに使うモデル。安くしたいときは claude-sonnet-5-5 など
MODEL = os.getenv("NOTE_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("NOTE_EFFORT", "high")
REVIEW_EFFORT = os.getenv("NOTE_REVIEW_EFFORT", "medium")

TOPICS_PATH = Path(os.getenv("NOTE_TOPICS", ROOT / "topics.json"))
PROFILE_PATH = Path(os.getenv("NOTE_PROFILE", ROOT / "profile.md"))
SELECTORS_PATH = Path(os.getenv("NOTE_SELECTORS", ROOT / "selectors.json"))
OUT_DIR = Path(os.getenv("NOTE_OUT_DIR", ROOT / "out"))          # 生成した記事（有料部分を含むので公開しない）
STATE_PATH = Path(os.getenv("NOTE_STATE", ROOT / "out" / "state.json"))
# Playwright のログイン状態（Cookie）。`python -m note_auto login` で作る。絶対に公開しない
STORAGE_STATE = Path(os.getenv("NOTE_STORAGE_STATE", ROOT / "out" / "note_storage.json"))

# 品質チェックの合格点（100点満点）と書き直しの最大回数
PASS_SCORE = int(os.getenv("NOTE_PASS_SCORE", "75"))
MAX_REWRITES = int(os.getenv("NOTE_MAX_REWRITES", "1"))

# 1日に投稿する上限（量産スパム扱いでアカウントが止まるのを避ける）
DAILY_LIMIT = int(os.getenv("NOTE_DAILY_LIMIT", "1"))

MIN_PRICE = 100     # note の有料記事の最低価格
MAX_PRICE = 50000
HEADLESS = os.getenv("NOTE_HEADLESS", "1") != "0"
# Playwright 同梱以外の Chrome/Chromium を使うとき（通常は空のまま）
CHROMIUM_PATH = os.getenv("NOTE_CHROMIUM_PATH") or None
