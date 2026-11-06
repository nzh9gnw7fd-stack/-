"""ルールベース抽出。

対応する書き方の例:
  「アグロエルフでマスター到達！15勝5敗」          → 使用報告 (wins=15, losses=5)
  「ランプドラゴン使用 vs スペルウィッチ 勝ち」    → 対戦記録
  「今日の戦績（進化ロイ）\n vs ナイメア ○\n vs クレスト ×」 → 対戦記録 x2
  「人形ネメに負けた…」（自分のデッキ不明）        → 自デッキ不明のため相手の使用率シグナルのみ
"""
from __future__ import annotations

import re

from ..archetypes import Catalog, norm
from . import DeckReport, Extraction, MatchRec

RE_RECORD = re.compile(r"(\d{1,3})\s*勝\s*(\d{1,3})\s*敗")
RE_RECORD_DASH = re.compile(r"(?<![\d/:])(\d{1,3})\s*[-－–]\s*(\d{1,3})(?![\d/:])")
RE_STREAK = re.compile(r"(\d{1,3})\s*連勝")
RE_VS = re.compile(r"(?:vs\.?|ｖｓ|対|相手[:：は]?)\s*", re.IGNORECASE)
RE_USING = re.compile(r"(使用|使って|で(?:マスター|グラマス|GM|AA|勝|連勝|到達|潜|回))")
RE_UNLIMITED = re.compile(r"アンリミ|アンリミテッド|unlimited", re.IGNORECASE)


def _deck_mentions(cat: Catalog, text: str) -> list[tuple[int, str]]:
    """テキスト中のデッキ名を出現位置付きで返す（長い別名を優先、重複除去）。"""
    n = norm(text)
    hits: list[tuple[int, int, str]] = []
    for a in cat.archetypes:
        for alias in sorted({a.name, *a.aliases}, key=len, reverse=True):
            an = norm(alias)
            if len(an) < 2:
                continue
            start = 0
            while (i := n.find(an, start)) >= 0:
                hits.append((i, i + len(an), a.name))
                start = i + len(an)
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out: list[tuple[int, str]] = []
    last_end = -1
    for s, e, name in hits:
        if s >= last_end:
            out.append((s, name))
            last_end = e
    return out


def _result_in(segment: str) -> str | None:
    s = norm(segment)
    # 記号は位置に関係なく、語は単語境界っぽく
    for m in ("○", "〇", "◯"):
        if m in segment:
            return "win"
    for m in ("×", "✕", "✖"):
        if m in segment:
            return "loss"
    if re.search(r"勝(ち|利|った|てた)|(?<![a-z])win(?![a-z])", s):
        return "win"
    if re.search(r"負け|敗北|(?<![a-z])(lose|loss)(?![a-z])", s):
        return "loss"
    return None


def extract(cat: Catalog, text: str) -> Extraction:
    ex = Extraction(extractor="rules")
    if RE_UNLIMITED.search(text):
        ex.format = "unlimited"
    rank = _rank_in_text(cat, text)

    mentions = _deck_mentions(cat, text)
    if not mentions:
        return ex

    # 自分のデッキ: 「使用」「で〜」の直前に出たデッキ、なければ vs 行以外で最初に出たデッキ
    lines = text.splitlines() or [text]
    own: str | None = None
    for line in lines:
        if RE_VS.search(line):
            continue
        ms = _deck_mentions(cat, line)
        if ms and RE_USING.search(line):
            own = ms[0][1]
            break
    if own is None:
        for line in lines:
            if RE_VS.search(line):
                continue
            ms = _deck_mentions(cat, line)
            if ms:
                own = ms[0][1]
                break

    # 対戦行: vs/対 の後ろのデッキ + 勝敗マーク
    for line in lines:
        vs = RE_VS.search(line)
        if not vs:
            continue
        tail = line[vs.end():]
        opp_ms = _deck_mentions(cat, tail)
        if not opp_ms:
            continue
        opp = opp_ms[0][1]
        head_ms = _deck_mentions(cat, line[: vs.start()])
        deck = head_ms[-1][1] if head_ms else own
        res = _result_in(line)
        if deck and res:
            ex.matches.append(MatchRec(deck=deck, opponent=opp, result=res, rank=rank, confidence=0.8))
        elif res and not deck:
            # 自デッキ不明 → 相手の使用率だけ記録
            ex.reports.append(DeckReport(deck=opp, rank=rank, confidence=0.5))

    # 「〇〇に負けた/勝った」形式（vs なし）
    if not ex.matches:
        for m in re.finditer(r"に(勝|負)", text):
            before = _deck_mentions(cat, text[: m.start()])
            if not before:
                continue
            opp = before[-1][1]
            res = "win" if m.group(1) == "勝" else "loss"
            if own and own != opp:
                ex.matches.append(MatchRec(deck=own, opponent=opp, result=res, rank=rank, confidence=0.6))
            else:
                ex.reports.append(DeckReport(deck=opp, rank=rank, confidence=0.5))

    # 集計報告: 15勝5敗 / 15-5 / 10連勝
    if own:
        rec = RE_RECORD.search(text) or (RE_RECORD_DASH.search(text) if not ex.matches else None)
        streak = RE_STREAK.search(text)
        if rec and not ex.matches:
            w, l = int(rec.group(1)), int(rec.group(2))
            if 0 < w + l <= 300:
                ex.reports.append(DeckReport(deck=own, rank=rank, wins=w, losses=l, confidence=0.8))
        elif streak and not ex.matches:
            # 連勝報告は勝ちに偏るので勝率には使わない（使用率のみ）
            ex.reports.append(DeckReport(deck=own, rank=rank, confidence=0.7))
        elif not ex.matches and not any(r.deck == own for r in ex.reports):
            ex.reports.append(DeckReport(deck=own, rank=rank, confidence=0.6))
    return ex


def _rank_in_text(cat: Catalog, text: str) -> str | None:
    n = norm(text)
    for rank in sorted(cat.rank_aliases, key=lambda r: -len(r)):
        for alias in cat.rank_aliases[rank]:
            an = norm(alias)
            if len(an) <= 2:
                # 「AA」「GM」などは英字の一部でないときだけ
                if re.search(rf"(?<![a-z]){re.escape(an)}(?![a-z])", n):
                    return rank
            elif an in n:
                return rank
    return None
