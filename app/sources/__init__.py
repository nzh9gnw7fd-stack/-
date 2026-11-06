"""データ源。各ソースは RawPost を返すだけにして、抽出・保存は pipeline が行う。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawPost:
    source: str            # "x" | "rss" | "manual" | "demo" | "structured"
    external_id: str       # ソース内で一意な ID（重複取り込み防止）
    text: str
    posted_at: str         # ISO8601 UTC
    author: str | None = None
    url: str | None = None
    # 既に構造化済みのデータ（大会結果CSVなど）。あればテキスト抽出をスキップする
    structured: dict[str, Any] | None = field(default=None)
