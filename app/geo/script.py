"""Claude で世界地理の長尺台本を書く（episodes/sample_geiranger.json と同じ形式）。"""
from __future__ import annotations

import json
import logging
import math
import os

from .. import config

log = logging.getLogger(__name__)

SYSTEM = """あなたは日本語の地理解説 YouTube チャンネルの構成作家兼ナレーション作家です。
世界のある土地について、地形のでき方・気候・歴史・人の暮らし・珍しい仕組み・生態系を、地理の専門用語を交えながら、
中学生にも伝わる言葉で解説する 9〜12 分の動画の台本を書きます。

構成:
- 冒頭30秒で「なぜ？」と思わせる問いを立て、最後にその答えが分かる流れにする。
- 6〜8 章。各章 2〜4 セグメント。1 セグメントのナレーションは 2〜4 文（80〜220 文字）。全体で 3600〜4800 文字。
- 地理用語（例: U字谷、カルスト、地溝帯、逆転層、内陸デルタ、ホットスポット）を 4〜6 個、term カードで丁寧に説明する。
- 最後の章で要点をまとめ、次回への引きとチャンネル登録のお願いを一言だけ入れる。

映像の指示（visual）:
- earth: 地球儀から目的地へズームする。動画の最初のセグメントは必ず earth。章の舞台が変わるときにも使う。
  lat/lon は渡された座標か、資料から確実に分かる地点だけ（目的地から 300km 以内）。zoom は 7（広域）〜13（街区）。
  2 回目以降の earth は start_from_previous を true にすると、前の場所から地球を回して移動する。
- photo: 現地の写真・映像を探す。query は英語で、固有名詞を含めた具体的な検索語（例: "Geirangerfjord Seven Sisters waterfall"）。
- term: 用語カード。term（用語）, reading（読み or 英語）, desc（60 文字以内の説明）。
- map: 衛星画像の静止画をゆっくり動かす（lat/lon/zoom）。
- 同じ種類を 3 回以上続けない。photo を全体の半分くらいにする。

事実について:
- 渡された資料（Wikipedia の抜粋）に書かれていることを中心に話す。資料にない数字・年号・固有名詞は使わない。
- 諸説あることは「〜と考えられています」「〜という説があります」と言う。
- 資料の文章をそのまま写さず、自分の言葉で説明する。
- 人々や文化を見下す表現、誇張したあおり（「ヤバすぎる」等）は使わない。
review には、事実確認が特に必要な箇所を自己申告する。"""


def _nullable(t: dict) -> dict:
    return {"anyOf": [t, {"type": "null"}]}


def schema() -> dict:
    visual = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["earth", "photo", "term", "map"]},
            "lat": _nullable({"type": "number"}), "lon": _nullable({"type": "number"}),
            "zoom": _nullable({"type": "number"}), "label": _nullable({"type": "string"}),
            "start_from_previous": _nullable({"type": "boolean"}),
            "query": _nullable({"type": "string"}), "term": _nullable({"type": "string"}),
            "reading": _nullable({"type": "string"}), "desc": _nullable({"type": "string"}),
        },
        "required": ["type", "lat", "lon", "zoom", "label", "start_from_previous", "query", "term", "reading", "desc"],
        "additionalProperties": False,
    }
    seg = {"type": "object", "properties": {"text": {"type": "string"}, "visual": visual},
           "required": ["text", "visual"], "additionalProperties": False}
    chapter = {"type": "object", "properties": {"title": {"type": "string"}, "segments": {"type": "array", "items": seg}},
               "required": ["title", "segments"], "additionalProperties": False}
    gloss = {"type": "object", "properties": {"term": {"type": "string"}, "desc": {"type": "string"}},
             "required": ["term", "desc"], "additionalProperties": False}
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "thumbnail_text": {"type": "string"},
            "summary": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "chapters": {"type": "array", "items": chapter},
            "glossary": {"type": "array", "items": gloss},
            "review": {"type": "string"},
        },
        "required": ["title", "thumbnail_text", "summary", "tags", "chapters", "glossary", "review"],
        "additionalProperties": False,
    }


def available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def write(topic: dict, research: dict) -> dict | None:
    import anthropic

    example = json.loads((config.ROOT / "episodes" / "sample_geiranger.json").read_text(encoding="utf-8"))
    example_short = {"title": example["title"], "thumbnail_text": example["thumbnail_text"],
                     "chapters": example["chapters"][:2]}
    lat, lon = research.get("lat"), research.get("lon")
    prompt = (
        f"テーマ: {topic['name']}\n切り口: {topic.get('angle', '')}\n"
        f"目的地の座標: lat={lat}, lon={lon}（最初の earth はここ、zoom={topic.get('zoom', 10)}）\n\n"
        f"<資料 lang=\"ja\" url=\"{research.get('ja', {}).get('url', '')}\">\n{research.get('ja', {}).get('text', '')}\n</資料>\n\n"
        f"<資料 lang=\"en\" url=\"{research.get('en', {}).get('url', '')}\">\n{research.get('en', {}).get('text', '')}\n</資料>\n\n"
        "台本の形式の見本（最初の2章だけ。内容は真似しない）:\n"
        + json.dumps(example_short, ensure_ascii=False)
        + "\n\ntitle は 50 文字以内で、地名と「何が分かるか」を入れる。thumbnail_text は改行（\\n）入りで 2 行・各 8 文字以内。"
          "tags は 8 個。summary は概要欄の冒頭に置く 2 文。")
    try:
        with anthropic.Anthropic().beta.messages.stream(
            model=os.getenv("SVWB_GEO_MODEL", config.LLM_MODEL),
            max_tokens=48000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": os.getenv("SVWB_GEO_EFFORT", "high"),
                           "format": {"type": "json_schema", "schema": schema()}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.RateLimitError as e:
        log.warning("Claude rate limited: %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s: %s", e.status_code, e.message)
        return None
    except anthropic.APIConnectionError as e:
        log.warning("Claude connection error: %s", e)
        return None
    if msg.stop_reason != "end_turn":
        log.warning("台本を作れませんでした: %s", msg.stop_reason)
        return None
    try:
        data = json.loads("".join(b.text for b in msg.content if b.type == "text"))
    except json.JSONDecodeError:
        return None
    return finalize(data, topic, research)


def _km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def finalize(data: dict, topic: dict, research: dict) -> dict:
    """AI の出力を検証して、ビルドできる形に整える（座標の暴走・空の映像指示を直す）。"""
    lat, lon = float(research["lat"]), float(research["lon"])
    for ci, ch in enumerate(data["chapters"]):
        for si, seg in enumerate(ch["segments"]):
            v = {k: val for k, val in seg["visual"].items() if val is not None}
            if ci == 0 and si == 0:
                v = {"type": "earth", "lat": lat, "lon": lon, "zoom": topic.get("zoom", 10), "label": topic["name"]}
            if v["type"] in ("earth", "map"):
                if "lat" not in v or "lon" not in v or _km(lat, lon, v["lat"], v["lon"]) > 300:
                    v["lat"], v["lon"] = lat, lon
                v["zoom"] = max(6.0, min(13.5, float(v.get("zoom") or topic.get("zoom", 10))))
            if v["type"] == "term" and not v.get("term"):
                v = {"type": "photo", "query": topic.get("wiki_en", topic["name"])}
            if v["type"] == "photo" and not v.get("query"):
                v["query"] = topic.get("wiki_en", topic["name"])
            seg["visual"] = v
    return {
        "slug": topic.get("wiki_en", topic["name"]).lower().replace(" ", "-"),
        "title": data["title"][:95],
        "thumbnail_text": data["thumbnail_text"],
        "thumbnail_zoom": topic.get("zoom", 10),
        "summary": data["summary"],
        "place": {"name": topic["name"], "name_en": topic.get("wiki_en", ""), "lat": lat, "lon": lon,
                  "country": topic.get("country", "")},
        "tags": data["tags"],
        "chapters": data["chapters"],
        "glossary": data["glossary"],
        "sources": research.get("sources", []),
        "review": data.get("review", ""),
    }
