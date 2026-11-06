"""デモ用の架空投稿ジェネレーター。

本物のデータ源が揃う前に、画面と集計の動作を確かめるためのもの。
「パック更新で新デッキが台頭し、旧トップが衰退する」流れと、デッキ間の相性、
ランク帯ごとの好みの違い（高ランクほどコントロール寄り、など）を再現する。
生成される投稿はすべて架空で、source="demo" として保存される。
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from ..archetypes import Catalog
from . import RawPost

TEMPLATES_MATCH = [
    "{deck}使用 vs {opp} {res_word}",
    "{deck}で{rank}帯潜ってる\nvs {opp} {mark}",
    "【{rank}】{deck} vs {opp} {mark}",
    "{deck}使ってます。vs{opp}{res_word}",
]
TEMPLATES_MULTI = "今日の戦績（{deck}）\n{lines}"
TEMPLATES_RECORD = [
    "{deck}で{rank}到達！ {w}勝{l}敗でした",
    "{deck}使用 {rank}帯 本日{w}勝{l}敗",
]
TEMPLATES_COMPLAIN = ["{opp}多すぎ…", "{opp}に負けた、{rank}帯きつい", "最近{opp}ばっか当たる"]
TEMPLATES_NOISE = ["ガチャ爆死した", "新カードのイラスト最高", "今日は大会見てた", "デイリー消化完了"]


def _rank_pref(name: str, rank_idx: int, n_ranks: int) -> float:
    """高ランクほどコントロール系、低ランクほどアグロ系が増える。"""
    t = rank_idx / max(1, n_ranks - 1)
    if any(k in name for k in ("アグロ", "フェイス", "テンポ", "海賊")):
        return 1.3 - 0.6 * t
    if any(k in name for k in ("コンボ", "ランプ", "守護", "秘術", "AF", "証拠", "クキシロ")):
        return 0.7 + 0.6 * t
    return 1.0


def generate(cat: Catalog, days: int = 21, posts_per_day: int = 220, seed: int = 7) -> list[RawPost]:
    """ローテーション（投稿の約8割）とアンリミテッド（約2割）の両方を作る。"""
    rot = _generate(cat, cat.archetype_names("rotation"), "", days, posts_per_day, seed)
    unl = _generate(cat, cat.archetype_names("unlimited"), "アンリミ ", days, max(1, posts_per_day // 4), seed + 1)
    return rot + unl


def _generate(cat: Catalog, names: list[str], prefix: str, days: int, posts_per_day: int, seed: int) -> list[RawPost]:
    rng = random.Random(seed)
    if len(names) < 3:
        return []
    ranks = cat.ranks
    rank_w = [0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.22, 0.08][: len(ranks)]

    # デッキ強度（隠れ変数）と相性ノイズ
    strength = {n: rng.gauss(0, 0.25) for n in names}
    matchup = {(a, b): rng.gauss(0, 0.35) for a in names for b in names}
    # 環境の流れ: 2デッキが途中から台頭、1デッキがナーフで衰退
    risers = rng.sample(names, 2 if len(names) > 4 else 1)
    faller = rng.choice([n for n in names if n not in risers])
    strength[faller] += 0.4
    shift_day = days // 2

    def popularity(name: str, day: int) -> float:
        base = math.exp(strength[name] * 2)
        if name in risers:
            base *= 0.2 + 1.8 / (1 + math.exp(-(day - shift_day) / 1.5))
        if name == faller:
            base *= 1.6 if day < shift_day else 0.5
        return base

    def p_win(a: str, b: str, day: int) -> float:
        sa = strength[a] - (0.5 if a == faller and day >= shift_day else 0)
        sb = strength[b] - (0.5 if b == faller and day >= shift_day else 0)
        x = sa - sb + matchup[(a, b)] - matchup[(b, a)]
        return 1 / (1 + math.exp(-x))

    authors = [f"@player{i:03d}" for i in range(400)]
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=days)
    out: list[RawPost] = []
    pid = 0
    for d in range(days):
        n_posts = int(posts_per_day * (0.8 + 0.4 * rng.random()) * (1.5 if d == shift_day else 1))
        for _ in range(n_posts):
            pid += 1
            ts = start + timedelta(days=d, minutes=rng.randint(0, 1439))
            ri = rng.choices(range(len(ranks)), weights=rank_w)[0]
            rank = ranks[ri]
            w = [popularity(n, d) * _rank_pref(n, ri, len(ranks)) for n in names]
            deck = rng.choices(names, weights=w)[0]
            author = rng.choice(authors)
            kind = rng.random()
            if kind < 0.55:
                opp = rng.choices(names, weights=w)[0]
                win = rng.random() < p_win(deck, opp, d)
                # SNS は勝ち報告が多い（報告バイアス）
                if not win and rng.random() < 0.3:
                    continue
                text = rng.choice(TEMPLATES_MATCH).format(
                    deck=deck, opp=opp, rank=rank,
                    res_word="勝ち" if win else "負け", mark="○" if win else "×",
                )
            elif kind < 0.7:
                lines = []
                for _ in range(rng.randint(3, 6)):
                    opp = rng.choices(names, weights=w)[0]
                    lines.append(f"vs {opp} {'○' if rng.random() < p_win(deck, opp, d) else '×'}")
                text = TEMPLATES_MULTI.format(deck=deck, lines="\n".join(lines)) + f"\n{rank}帯"
            elif kind < 0.82:
                n = rng.randint(8, 30)
                avg = sum(p_win(deck, o, d) * wi for o, wi in zip(names, w)) / sum(w)
                wins = sum(rng.random() < avg for _ in range(n))
                text = rng.choice(TEMPLATES_RECORD).format(deck=deck, rank=rank, w=wins, l=n - wins)
            elif kind < 0.92:
                opp = rng.choices(names, weights=w)[0]
                text = rng.choice(TEMPLATES_COMPLAIN).format(opp=opp, rank=rank)
            else:
                text = rng.choice(TEMPLATES_NOISE)
            if prefix and kind < 0.92:
                text = prefix + text
            out.append(RawPost("demo", f"demo-{seed}-{pid}", text, ts.strftime("%Y-%m-%dT%H:%M:%SZ"), author))
    return out
