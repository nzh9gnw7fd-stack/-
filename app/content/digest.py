"""集計結果を1本のコンテンツ分の「ネタ」にまとめる。

データが薄い日にランキング動画を出すと、間違った情報でチャンネルの信用を落とす。
そこで直近 7→14→30 日の順に、十分な件数がある最短の期間を選び、
どの期間でも足りなければ publishable=False にして投稿を止める。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .. import aggregate
from ..archetypes import catalog
from . import video_settings

JST = timezone(timedelta(hours=9))
WINDOWS = (7, 14, 30)


@dataclass
class Digest:
    date: str                      # JST の日付 YYYY-MM-DD
    days: int                      # 集計期間
    fmt: str
    samples: float                 # 使用率の分母（重み付きの登場回数）
    games: float                   # 勝率に使える対戦数
    decks: list[dict]
    matchups: dict
    ranks: dict
    summary: dict
    publishable: bool = True
    reasons: list[str] = field(default_factory=list)

    # ---- ネタの切り出し ----
    def top(self, n: int = 5) -> list[dict]:
        return self.decks[:n]

    def risers(self, n: int = 3) -> list[dict]:
        return [d for d in sorted(self.decks, key=lambda d: -d["trend"]) if d["trend"] >= 0.02][:n]

    def fallers(self, n: int = 3) -> list[dict]:
        return [d for d in sorted(self.decks, key=lambda d: d["trend"]) if d["trend"] <= -0.02][:n]

    def strong(self, n: int = 3, min_games: float = 15) -> list[dict]:
        """勝率の信頼区間がそれなりに狭いデッキを推定勝率順に。"""
        ok = [d for d in self.decks if d["games"] >= min_games]
        return sorted(ok, key=lambda d: -d["winrate"])[:n]

    def notable_matchups(self, n: int = 3, min_games: float = 8) -> list[dict]:
        out = []
        decks, grid = self.matchups.get("decks", []), self.matchups.get("grid", [])
        for i, a in enumerate(decks):
            for j, b in enumerate(decks):
                c = grid[i][j] if i < len(grid) and j < len(grid[i]) else None
                if c and i < j and c["games"] >= min_games:
                    out.append({"deck": a, "opponent": b, **c})
        # 50% から遠いもの＝はっきり有利不利がある組み合わせ
        out.sort(key=lambda m: -abs(m["winrate"] - 0.5))
        return [m if m["winrate"] >= 0.5 else _flip(m) for m in out[:n]]

    def top_rank_meta(self) -> tuple[str, dict] | None:
        """件数が十分ある中で一番高いランク帯の分布。"""
        for rank, v in self.ranks.items():
            if rank != "不明" and v["samples"] >= 10:
                return rank, v
        return None

    @property
    def date_label(self) -> str:
        d = datetime.strptime(self.date, "%Y-%m-%d")
        return f"{d.month}/{d.day}"


def _flip(m: dict) -> dict:
    return {**m, "deck": m["opponent"], "opponent": m["deck"], "winrate": round(1 - m["winrate"], 4),
            "raw": round(1 - m["raw"], 4), "ci_low": round(1 - m["ci_high"], 4), "ci_high": round(1 - m["ci_low"], 4)}


def build(conn: sqlite3.Connection, fmt: str = "rotation", end: datetime | None = None,
          min_samples: float | None = None) -> Digest:
    end = end or datetime.now(timezone.utc)
    need = float(video_settings()["min_samples"] if min_samples is None else min_samples)
    chosen = None
    for days in WINDOWS:
        f = aggregate.Filters(format=fmt, days=days, end=end)
        ts = aggregate.share_timeseries(conn, f)
        samples = sum(ts["samples"])
        chosen = (f, samples)
        if samples >= need:
            break
    f, samples = chosen
    decks = aggregate.deck_stats(conn, f)
    cat = catalog()
    for d in decks:
        d["class"] = d.get("class") or cat.class_of(d["deck"])
    dg = Digest(
        date=end.astimezone(JST).strftime("%Y-%m-%d"),
        days=f.days,
        fmt=fmt,
        samples=round(samples, 1),
        games=round(sum(d["games"] for d in decks) / 2, 1),
        decks=decks,
        matchups=aggregate.matchups(conn, f, top=8),
        ranks=aggregate.rank_breakdown(conn, f),
        summary=aggregate.summary(conn, f),
    )
    if samples < need:
        dg.publishable = False
        dg.reasons.append(f"直近{f.days}日の集計対象が {samples:.0f} 件で、基準の {need:.0f} 件に足りません")
    if len(decks) < 3:
        dg.publishable = False
        dg.reasons.append(f"登場したデッキが {len(decks)} 種類しかありません")
    return dg
