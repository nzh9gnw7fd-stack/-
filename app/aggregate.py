"""集計ロジック。

偏りへの対策:
1. 対戦記録は「自分視点」と「相手視点」の両方で数える。SNS は勝ち報告が多いので
   自分視点の勝率は高く出るが、同じ試合を相手側から見ると低く出る。両方を足すと
   全体の勝率はちょうど 50% になり、報告バイアスがある程度打ち消される。
2. 1人の投稿者が1日に寄与できる重みに上限をかける（AUTHOR_DAILY_CAP）。
3. 勝率は Beta(k, k) 事前分布で 50% 側に縮めた値（shrunk）を主に表示し、
   生の勝率には Wilson の 95% 信頼区間を付ける。
"""
from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import config
from .archetypes import catalog

JST = timezone(timedelta(hours=9))


@dataclass
class Filters:
    format: str = "rotation"
    ranks: list[str] | None = None     # None = 全ランク
    days: int = 14                     # 直近 N 日
    min_conf: float = 0.5
    end: datetime | None = None        # 集計の終端（デフォルトは現在）

    def window(self) -> tuple[str, str]:
        end = self.end or datetime.now(timezone.utc)
        start = end - timedelta(days=self.days)
        f = "%Y-%m-%dT%H:%M:%SZ"
        return start.strftime(f), end.strftime(f)


def _day(ts: str) -> str:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone(JST).strftime("%Y-%m-%d")


def wilson(wins: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom)


def shrink(wins: float, n: float, k: float | None = None) -> float:
    k = config.WINRATE_PRIOR_K if k is None else k
    return (wins + k) / (n + 2 * k)


# ---- データ取得 ----
def _rows(conn: sqlite3.Connection, f: Filters):
    start, end = f.window()
    rank_sql, rank_args = "", []
    if f.ranks:
        rank_sql = f" AND rank IN ({','.join('?' * len(f.ranks))})"
        rank_args = list(f.ranks)
    matches = conn.execute(
        "SELECT played_at AS ts, author, deck, opponent, result, rank FROM matches"
        f" WHERE format = ? AND confidence >= ? AND played_at >= ? AND played_at < ?{rank_sql}",
        [f.format, f.min_conf, start, end, *rank_args],
    ).fetchall()
    reports = conn.execute(
        "SELECT reported_at AS ts, author, deck, rank, wins, losses FROM deck_reports"
        f" WHERE format = ? AND confidence >= ? AND reported_at >= ? AND reported_at < ?{rank_sql}",
        [f.format, f.min_conf, start, end, *rank_args],
    ).fetchall()
    return matches, reports


def _author_weights(matches, reports) -> dict[tuple[str, str], float]:
    """(author, day) ごとの重み。上限を超えた分は按分で薄める。"""
    counts: dict[tuple[str, str], float] = defaultdict(float)
    for m in matches:
        counts[(m["author"] or "?", _day(m["ts"]))] += 1
    for r in reports:
        n = (r["wins"] or 0) + (r["losses"] or 0)
        counts[(r["author"] or "?", _day(r["ts"]))] += max(1, n)
    cap = config.AUTHOR_DAILY_CAP
    return {k: min(1.0, cap / v) for k, v in counts.items()}


# ---- 使用率 ----
def _appearances(matches, reports, weights):
    """(day, rank, deck, weight) の列。対戦記録は自分と相手の両方を1回ずつ数える。"""
    for m in matches:
        day = _day(m["ts"])
        w = weights[(m["author"] or "?", day)]
        yield day, m["rank"], m["deck"], w
        if m["opponent"]:
            yield day, m["rank"], m["opponent"], w
    for r in reports:
        day = _day(r["ts"])
        yield day, r["rank"], r["deck"], weights[(r["author"] or "?", day)]


def share_timeseries(conn: sqlite3.Connection, f: Filters) -> dict:
    matches, reports = _rows(conn, f)
    weights = _author_weights(matches, reports)
    per_day: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for day, _rank, deck, w in _appearances(matches, reports, weights):
        per_day[day][deck] += w
    days = sorted(per_day)
    decks = sorted({d for v in per_day.values() for d in v}, key=lambda d: -sum(v.get(d, 0) for v in per_day.values()))
    series = {}
    for deck in decks:
        series[deck] = [
            round(per_day[d].get(deck, 0) / s, 4) if (s := sum(per_day[d].values())) else 0 for d in days
        ]
    totals = [round(sum(per_day[d].values()), 1) for d in days]
    return {"days": days, "series": series, "samples": totals}


def rank_breakdown(conn: sqlite3.Connection, f: Filters) -> dict:
    f2 = Filters(f.format, None, f.days, f.min_conf, f.end)
    matches, reports = _rows(conn, f2)
    weights = _author_weights(matches, reports)
    per_rank: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for _day_, rank, deck, w in _appearances(matches, reports, weights):
        per_rank[rank or "不明"][deck] += w
    cat = catalog()
    order = [r for r in reversed(cat.ranks) if r in per_rank] + (["不明"] if "不明" in per_rank else [])
    out = {}
    for r in order:
        tot = sum(per_rank[r].values())
        out[r] = {
            "samples": round(tot, 1),
            "share": dict(sorted(((d, round(v / tot, 4)) for d, v in per_rank[r].items()), key=lambda x: -x[1])),
        }
    return out


# ---- 勝率・相性 ----
def _pair_records(matches, reports, weights):
    """(deck, opponent|None, wins, n) を返す。対戦は両視点、集計報告は自分視点のみ。"""
    for m in matches:
        w = weights[(m["author"] or "?", _day(m["ts"]))]
        won = 1.0 if m["result"] == "win" else 0.0
        yield m["deck"], m["opponent"], won * w, w
        if m["opponent"]:
            yield m["opponent"], m["deck"], (1 - won) * w, w
    for r in reports:
        if r["wins"] is None or r["losses"] is None:
            continue
        w = weights[(r["author"] or "?", _day(r["ts"]))]
        yield r["deck"], None, r["wins"] * w, (r["wins"] + r["losses"]) * w


def deck_stats(conn: sqlite3.Connection, f: Filters) -> list[dict]:
    matches, reports = _rows(conn, f)
    weights = _author_weights(matches, reports)
    wins: dict[str, float] = defaultdict(float)
    n: dict[str, float] = defaultdict(float)
    for deck, opp, w, cnt in _pair_records(matches, reports, weights):
        if opp == deck:
            continue  # ミラーは勝率に入れない
        wins[deck] += w
        n[deck] += cnt

    # 使用率（直近期間全体）とトレンド（直近3日 vs その前）
    share_total: dict[str, float] = defaultdict(float)
    recent: dict[str, float] = defaultdict(float)
    prior: dict[str, float] = defaultdict(float)
    end = f.end or datetime.now(timezone.utc)
    cut = (end - timedelta(days=3)).astimezone(JST).strftime("%Y-%m-%d")
    for day, _r, deck, w in _appearances(matches, reports, weights):
        share_total[deck] += w
        (recent if day >= cut else prior)[deck] += w
    tot, rt, pt = sum(share_total.values()) or 1, sum(recent.values()) or 1, sum(prior.values()) or 1

    cat = catalog()
    out = []
    for deck in sorted(share_total, key=lambda d: -share_total[d]):
        lo, hi = wilson(wins[deck], n[deck])
        out.append({
            "deck": deck,
            "class": cat.class_of(deck),
            "share": round(share_total[deck] / tot, 4),
            "share_recent": round(recent[deck] / rt, 4),
            "share_prior": round(prior[deck] / pt, 4),
            "trend": round(recent[deck] / rt - prior[deck] / pt, 4),
            "games": round(n[deck], 1),
            "winrate_raw": round(wins[deck] / n[deck], 4) if n[deck] else None,
            "winrate": round(shrink(wins[deck], n[deck]), 4),
            "ci_low": round(lo, 4),
            "ci_high": round(hi, 4),
        })
    return out


def matchups(conn: sqlite3.Connection, f: Filters, top: int = 10) -> dict:
    matches, reports = _rows(conn, f)
    weights = _author_weights(matches, reports)
    wins: dict[tuple[str, str], float] = defaultdict(float)
    n: dict[tuple[str, str], float] = defaultdict(float)
    for deck, opp, w, cnt in _pair_records(matches, [], weights):
        if opp:
            wins[(deck, opp)] += w
            n[(deck, opp)] += cnt
    decks = [d["deck"] for d in deck_stats(conn, f)[:top]]
    grid = []
    for a in decks:
        row = []
        for b in decks:
            k = (a, b)
            if a == b or not n[k]:
                row.append(None)
                continue
            lo, hi = wilson(wins[k], n[k])
            row.append({
                "winrate": round(shrink(wins[k], n[k], k=config.WINRATE_PRIOR_K / 2), 4),
                "raw": round(wins[k] / n[k], 4),
                "games": round(n[k], 1),
                "ci_low": round(lo, 4),
                "ci_high": round(hi, 4),
            })
        grid.append(row)
    return {"decks": decks, "grid": grid}


def summary(conn: sqlite3.Connection, f: Filters) -> dict:
    start, end = f.window()
    q = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731
    by_source = {
        r["source"]: r["c"]
        for r in conn.execute(
            "SELECT source, COUNT(*) c FROM posts WHERE posted_at >= ? AND posted_at < ? GROUP BY source", (start, end)
        )
    }
    by_extractor = {
        (r["extractor"] or "未処理"): r["c"]
        for r in conn.execute(
            "SELECT extractor, COUNT(*) c FROM posts WHERE posted_at >= ? AND posted_at < ? GROUP BY extractor",
            (start, end),
        )
    }
    return {
        "posts": sum(by_source.values()),
        "by_source": by_source,
        "by_extractor": by_extractor,
        "matches": q("SELECT COUNT(*) FROM matches WHERE format=? AND played_at >= ? AND played_at < ?",
                     f.format, start, end),
        "reports": q("SELECT COUNT(*) FROM deck_reports WHERE format=? AND reported_at >= ? AND reported_at < ?",
                     f.format, start, end),
        "pending": q("SELECT COUNT(*) FROM posts WHERE extracted = 0"),
        "last_post": q("SELECT MAX(posted_at) FROM posts"),
        "last_fetch": q("SELECT MAX(fetched_at) FROM posts"),
    }
