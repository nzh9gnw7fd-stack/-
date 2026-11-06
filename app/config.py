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

# RSS/Atom フィード（カンマ区切り）。攻略ブログ・note などの更新を拾う
RSS_FEEDS = [u.strip() for u in os.getenv("SVWB_RSS_FEEDS", "").split(",") if u.strip()]

# 収集の間隔（分）
POLL_MINUTES = int(os.getenv("SVWB_POLL_MINUTES", "30"))

# 集計パラメータ
# 1人の投稿者が1日に寄与できる対戦数の上限（声の大きい人による偏りを抑える）
AUTHOR_DAILY_CAP = int(os.getenv("SVWB_AUTHOR_DAILY_CAP", "20"))
# 勝率の事前分布 Beta(k, k)。サンプルが少ないデッキの勝率を 50% 側に縮める
WINRATE_PRIOR_K = float(os.getenv("SVWB_PRIOR_K", "10"))
