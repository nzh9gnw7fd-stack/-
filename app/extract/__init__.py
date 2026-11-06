"""投稿テキストから対戦記録・デッキ使用報告を抽出する。

- rules.py : 正規表現と辞書による抽出（無料・高速・取りこぼし多め）
- llm.py   : Claude による抽出（表記ゆれや文脈に強い・有料）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MatchRec:
    deck: str
    result: Literal["win", "loss"]
    opponent: str | None = None
    rank: str | None = None
    confidence: float = 1.0


@dataclass
class DeckReport:
    deck: str
    rank: str | None = None
    wins: int | None = None
    losses: int | None = None
    confidence: float = 1.0


@dataclass
class Extraction:
    matches: list[MatchRec] = field(default_factory=list)
    reports: list[DeckReport] = field(default_factory=list)
    format: str = "rotation"
    extractor: str = "rules"

    @property
    def empty(self) -> bool:
        return not self.matches and not self.reports
