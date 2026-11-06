"""アプリ全体の設定。環境変数で上書きできる。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("SVWB_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("SVWB_DB_PATH", DATA_DIR / "meta.db"))
ARCHETYPES_PATH = Path(os.getenv("SVWB_ARCHETYPES", ROOT / "archetypes.json"))

# LLM 抽出（ANTHROPIC_API_KEY 等の認証情報が無ければルールベースのみで動く）
LLM_ENABLED = os.getenv("SVWB_LLM", "auto")  # auto | on | off
LLM_MODEL = os.getenv("SVWB_LLM_MODEL", "claude-opus-5-5")
LLM_EFFORT = os.getenv("SVWB_LLM_EFFORT", "low")
LLM_BATCH_SIZE = int(os.getenv("SVWB_LLM_BATCH", "20"))

# X API v2（任意・有料）
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
X_QUERY = os.getenv(
    "SVWB_X_QUERY",
    '(シャドバ OR シャドウバース OR #シャドバWB OR #ShadowverseWB) (勝 OR 負 OR 連勝 OR マスター OR デッキ) -is:retweet lang:ja',
)

# 無料データ源の設定ファイル（Mastodon / Misskey / Bluesky / RSS）
SOURCES_PATH = Path(os.getenv("SVWB_SOURCES", ROOT / "sources.json"))
# SNS 収集を有効にするか（ローカル開発で勝手に外部へ取りに行かないよう、既定は off。Actions では on にする）
SOCIAL_ENABLED = os.getenv("SVWB_SOCIAL", "off") == "on"


def sources_config() -> dict:
    import json

    try:
        return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# RSS/Atom フィード。環境変数（カンマ区切り）と sources.json の両方から読む
RSS_FEEDS = [u.strip() for u in os.getenv("SVWB_RSS_FEEDS", "").split(",") if u.strip()]
if SOCIAL_ENABLED:
    RSS_FEEDS += [u for u in sources_config().get("rss", {}).get("feeds", []) if u not in RSS_FEEDS]

# GitHub Actions 用のアーカイブと手動投入フォルダ
ARCHIVE_DIR = Path(os.getenv("SVWB_ARCHIVE_DIR", ROOT / "archive"))
MANUAL_DIR = Path(os.getenv("SVWB_MANUAL_DIR", ROOT / "manual"))

# 収集の間隔（分）
POLL_MINUTES = int(os.getenv("SVWB_POLL_MINUTES", "30"))

# 集計パラメータ
# 1人の投稿者が1日に寄与できる対戦数の上限（声の大きい人による偏りを抑える）
AUTHOR_DAILY_CAP = int(os.getenv("SVWB_AUTHOR_DAILY_CAP", "20"))
# 勝率の事前分布 Beta(k, k)。サンプルが少ないデッキの勝率を 50% 側に縮める
WINRATE_PRIOR_K = float(os.getenv("SVWB_PRIOR_K", "10"))
