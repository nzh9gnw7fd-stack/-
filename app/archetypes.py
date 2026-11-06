"""アーキタイプ辞書の読み込みと名前の正規化。"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import config


def norm(text: str) -> str:
    """全角/半角・大小文字の揺れを吸収する。"""
    return unicodedata.normalize("NFKC", text).lower().strip()


@dataclass
class Archetype:
    name: str
    cls: str
    aliases: list[str] = field(default_factory=list)
    key_cards: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=lambda: ["rotation", "unlimited"])


@dataclass
class Catalog:
    classes: dict[str, list[str]]
    ranks: list[str]
    rank_aliases: dict[str, list[str]]
    archetypes: list[Archetype]

    # ---- 正規化 ----
    def archetype_names(self, fmt: str | None = None) -> list[str]:
        return [a.name for a in self.archetypes if fmt is None or fmt in a.formats]

    def class_of(self, archetype: str) -> str | None:
        for a in self.archetypes:
            if a.name == archetype:
                return a.cls
        if archetype.startswith("その他"):
            return archetype.removeprefix("その他")
        return None

    def resolve_archetype(self, raw: str | None, cls_hint: str | None = None) -> str | None:
        """表記ゆれを含むデッキ名を正規名に変換。不明ならクラス名から「その他◯◯」にする。"""
        if not raw:
            return None
        n = norm(raw)
        best: tuple[int, str] | None = None
        for a in self.archetypes:
            for alias in [a.name, *a.aliases]:
                an = norm(alias)
                if an == n:
                    return a.name
                if an and an in n and (best is None or len(an) > best[0]):
                    best = (len(an), a.name)
        if best:
            return best[1]
        cls = self.resolve_class(raw) or cls_hint
        return f"その他{cls}" if cls else None

    def resolve_class(self, raw: str | None) -> str | None:
        if not raw:
            return None
        n = norm(raw)
        for cls, aliases in self.classes.items():
            # 1文字の略称（E/R/W...）は誤検出が多いので完全一致のみ
            for alias in aliases:
                an = norm(alias)
                if (len(an) <= 2 and n == an) or (len(an) > 2 and an in n):
                    return cls
        return None

    def resolve_rank(self, raw: str | None) -> str | None:
        if not raw:
            return None
        n = norm(raw)
        for r in self.ranks:
            if norm(r) == n:
                return r
        # 長いランク名（グランドマスター）を先に評価する
        for rank in sorted(self.rank_aliases, key=lambda r: -len(r)):
            for alias in self.rank_aliases[rank]:
                if norm(alias) == n or (len(alias) > 2 and norm(alias) in n):
                    return rank
        return None

    def from_cards(self, card_names: list[str]) -> str | None:
        """カード名リストからキーカードの一致数が最も多いアーキタイプを選ぶ。"""
        cards = {norm(c) for c in card_names}
        scored = []
        for a in self.archetypes:
            if not a.key_cards:
                continue
            hit = sum(1 for k in a.key_cards if norm(k) in cards)
            if hit:
                scored.append((hit / len(a.key_cards), a.name))
        return max(scored)[1] if scored else None


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> Catalog:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Catalog(
        classes=raw["classes"],
        ranks=raw["ranks"],
        rank_aliases=raw.get("rank_aliases", {}),
        archetypes=[
            Archetype(a["name"], a["class"], a.get("aliases", []), a.get("key_cards", []),
                      a.get("formats", ["rotation", "unlimited"]))
            for a in raw["archetypes"]
        ],
    )


def catalog() -> Catalog:
    """ファイルが更新されたら自動で読み直す。"""
    p = config.ARCHETYPES_PATH
    return _load(str(p), p.stat().st_mtime)
