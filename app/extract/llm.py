"""Claude による投稿の構造化抽出。

複数の投稿をまとめて1リクエストで処理し、JSON Schema（構造化出力）で
デッキ名を辞書の正規名に限定する。認証情報が無い・失敗した場合は None を返し、
呼び出し側はルールベース抽出にフォールバックする。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from .. import config
from ..archetypes import Catalog
from . import DeckReport, Extraction, MatchRec

log = logging.getLogger(__name__)

SYSTEM = """あなたは『Shadowverse: Worlds Beyond』の対戦報告を読み取るアナリストです。
SNS やブログの投稿から、ランクマッチの対戦記録とデッキ使用報告を抜き出します。

ルール:
- 投稿者自身が使ったデッキを deck、対戦相手のデッキを opponent にする。
- デッキ名は必ず与えられた候補から選ぶ。候補にないがクラスは分かる場合は「その他<クラス名>」。クラスも分からなければその対戦は出力しない。
- 1試合ごとの勝敗が読み取れるものは matches に入れる（相手不明なら opponent は null）。
- 「15勝5敗」のような集計しかないもの、または勝敗のないデッキ使用報告は reports に入れる。
  連勝報告など勝ちだけを報告しているものは wins/losses を null にする（勝率に偏りが出るため）。
- 相手デッキへの愚痴（「〇〇多すぎ」「〇〇に負けた」）で自分のデッキが不明なら、その相手デッキを reports に deck として入れる（使用率シグナル）。
- rank はランク候補から選ぶ。書かれていなければ null。
- フォーマットはアンリミテッドの記載があれば unlimited、それ以外は rotation。
- 対戦と関係のない投稿（ガチャ、イラスト、雑談、ネタ、他ゲーム）は matches も reports も空にする。
- 推測で埋めない。曖昧なら confidence を下げる（0〜1）。"""


def available() -> bool:
    if config.LLM_ENABLED == "off":
        return False
    if config.LLM_ENABLED == "on":
        return True
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


def _schema(cat: Catalog) -> dict[str, Any]:
    decks = cat.archetype_names() + [f"その他{c}" for c in cat.classes]
    deck = {"type": "string", "enum": decks}
    rank = _nullable({"type": "string", "enum": cat.ranks})
    match = {
        "type": "object",
        "properties": {
            "deck": deck,
            "opponent": _nullable(deck),
            "result": {"type": "string", "enum": ["win", "loss"]},
            "rank": rank,
            "confidence": {"type": "number"},
        },
        "required": ["deck", "opponent", "result", "rank", "confidence"],
        "additionalProperties": False,
    }
    report = {
        "type": "object",
        "properties": {
            "deck": deck,
            "rank": rank,
            "wins": _nullable({"type": "integer"}),
            "losses": _nullable({"type": "integer"}),
            "confidence": {"type": "number"},
        },
        "required": ["deck", "rank", "wins", "losses", "confidence"],
        "additionalProperties": False,
    }
    post = {
        "type": "object",
        "properties": {
            "index": {"type": "integer"},
            "format": {"type": "string", "enum": ["rotation", "unlimited"]},
            "matches": {"type": "array", "items": match},
            "reports": {"type": "array", "items": report},
        },
        "required": ["index", "format", "matches", "reports"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"posts": {"type": "array", "items": post}},
        "required": ["posts"],
        "additionalProperties": False,
    }


def _client():
    import anthropic

    return anthropic.Anthropic()


def extract_batch(cat: Catalog, texts: list[str]) -> list[Extraction] | None:
    """texts と同じ長さのリストを返す。失敗時は None。"""
    if not texts:
        return []
    import anthropic

    deck_list = "\n".join(f"- {a.name}（{a.cls}）別名: {'、'.join(a.aliases)}" for a in cat.archetypes)
    # 辞書部分は投稿ごとに変わらないので system 側に置き、プロンプトキャッシュを効かせる
    system = [
        {"type": "text", "text": SYSTEM},
        {
            "type": "text",
            "text": f"デッキ候補:\n{deck_list}\n\nランク候補: {'、'.join(cat.ranks)}",
            "cache_control": {"type": "ephemeral"},
        },
    ]
    body = "\n\n".join(f"<post index=\"{i}\">\n{t}\n</post>" for i, t in enumerate(texts))
    try:
        resp = _client().beta.messages.create(
            model=config.LLM_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": f"次の {len(texts)} 件の投稿を処理してください。\n\n{body}"}],
            output_config={
                "effort": config.LLM_EFFORT,
                "format": {"type": "json_schema", "schema": _schema(cat)},
            },
            # 安全分類器による誤拒否時はサーバー側で別モデルに再実行させる
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        log.warning("Claude rate limited: %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s: %s", e.status_code, e.message)
        return None
    except anthropic.APIConnectionError as e:
        log.warning("Claude connection error: %s", e)
        return None
    except TypeError as e:  # 認証情報が見つからない
        log.warning("Claude client not configured: %s", e)
        return None

    if resp.stop_reason == "refusal":
        log.warning("Claude refused batch: %s", getattr(resp, "stop_details", None))
        return None
    if resp.stop_reason == "max_tokens":
        log.warning("Claude output truncated; retry with a smaller batch")
        return None

    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Claude returned invalid JSON")
        return None

    out = [Extraction(extractor="llm") for _ in texts]
    for p in data.get("posts", []):
        i = p.get("index")
        if not isinstance(i, int) or not 0 <= i < len(texts):
            continue
        ex = out[i]
        ex.format = p.get("format", "rotation")
        for m in p.get("matches", []):
            ex.matches.append(
                MatchRec(m["deck"], m["result"], m.get("opponent"), m.get("rank"), _clip(m.get("confidence")))
            )
        for r in p.get("reports", []):
            ex.reports.append(
                DeckReport(r["deck"], r.get("rank"), r.get("wins"), r.get("losses"), _clip(r.get("confidence")))
            )
    return out


def _clip(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.7
