"""話題ネタ（悩み・コンプレックス・興味関心）のショート台本を Claude で書く。

伸びている動画の「タイトルの型」と「刺さっている悩み」だけを参考にし、中身はオリジナルで書く
（他人の動画の文章を写さない）。各ジャンルの guard（医療・投資の断定禁止など）をプロンプトに入れ、
AI 自身にもリスクを自己申告させる。リスクが高いもの・事実確認が要るものは自動投稿せず
「確認待ち」に回す（publishable=False）。
"""
from __future__ import annotations

import json
import logging
import os
import random

from .. import config
from .trends import Idea, niches, topics_config
from .writer import Scene, Script

log = logging.getLogger(__name__)

NICHE_COLORS = {"money": "#e0b234", "work": "#5b7ff0", "love": "#e87ba4", "selfcare": "#3cc7d6",
                "health": "#3fb56b", "mind": "#a05cd6", "trivia": "#e8743b", "ai_tools": "#2a78d6",
                "game_svwb": "#8e8d86"}

SYSTEM = """あなたは日本語の YouTube ショート／TikTok の構成作家です。視聴者の悩みや「知りたい」に正面から応える、
30〜45秒の役に立つ縦型動画の台本を書きます。

方針:
- 冒頭1文（hook）で「自分のことだ」と思わせる。疑問・意外な事実・共感（あるある）のどれかを使う。
- 本編は3〜4個のポイント。各ポイントは見出し（12文字以内）と、読み上げる説明（40文字以内）。具体的で、今日から試せる内容にする。
- 最後に、保存やフォローを促す一言（押しつけがましくなく）。
- 参考に渡す「伸びている動画のタイトル」は、どんな悩みが求められているかを知るためだけに使う。文章を写さない。
- 事実として言うことは、広く確認されている一般的な知識だけ。数字・統計・研究結果は、確実なものでなければ使わない。
- 誇張・断定・不安のあおりはしない（「絶対」「必ず」「〇〇しないと人生終わる」など）。
- 外見・体型・年齢・性別・職業などで人を笑ったり見下したりしない。コンプレックスには寄り添う姿勢で書く。
- 医療・投資・法律の個別の助言はしない。必要なら専門家への相談を勧める。

risk には内容のリスクを自己申告する: low（一般的なライフハック・雑学）/ medium（健康・お金・心理などで、表現に注意が要る）/
high（事実確認しないと誤情報になりうる・センシティブ）。needs_fact_check は、具体的な数字や事実の主張を含むなら true。"""


def _schema() -> dict:
    point = {"type": "object", "properties": {"head": {"type": "string"}, "say": {"type": "string"}},
             "required": ["head", "say"], "additionalProperties": False}
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "hook": {"type": "string"},
            "hook_screen": {"type": "string"},
            "points": {"type": "array", "items": point},
            "outro": {"type": "string"},
            "description": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "risk": {"type": "string", "enum": ["low", "medium", "high"]},
            "needs_fact_check": {"type": "boolean"},
            "risk_note": {"type": "string"},
        },
        "required": ["title", "hook", "hook_screen", "points", "outro", "description", "hashtags", "risk",
                     "needs_fact_check", "risk_note"],
        "additionalProperties": False,
    }


def available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def write(idea: Idea, date: str) -> tuple[Script, dict] | None:
    """(台本, 審査情報) を返す。失敗時は None。"""
    import anthropic

    n = niches().get(idea.niche, {})
    hooks = topics_config().get("hooks", [])
    rnd = random.Random(f"{date}-{idea.topic}")
    examples = "\n".join(f"- {e.title}（{e.views:,}回）" if e.views else f"- {e.title}" for e in idea.evidence[:5])
    prompt = (f"ジャンル: {n.get('label', idea.niche)}\nテーマ: {idea.topic}\n"
              f"いま反応が集まっている悩み・関心: {'、'.join(idea.pains) or '（特になし）'}\n"
              f"伸びている動画・検索（参考。写さない）:\n{examples or '- なし'}\n"
              f"使ってよいフックの型（例）: {' / '.join(rnd.sample(hooks, min(3, len(hooks))))}\n"
              f"このジャンルの注意: {n.get('guard', '')}\n\n"
              "title は全角40文字以内で、検索されやすい言葉を前に。hook_screen は画面に大きく出す15文字以内の文字。"
              "description は3〜5行（最後に『※個人差があります』等の注意が必要なら入れる）。hashtags は5個（#なし）。")
    try:
        resp = anthropic.Anthropic().beta.messages.create(
            model=os.getenv("SVWB_CONTENT_MODEL", config.LLM_MODEL),
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": os.getenv("SVWB_CONTENT_EFFORT", "medium"),
                           "format": {"type": "json_schema", "schema": _schema()}},
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
    if resp.stop_reason in ("refusal", "max_tokens"):
        log.warning("台本を作れませんでした（%s）: %s", resp.stop_reason, idea.topic)
        return None
    try:
        data = json.loads("".join(b.text for b in resp.content if b.type == "text"))
    except json.JSONDecodeError:
        return None
    return to_script(idea, data), {
        "risk": data["risk"], "needs_fact_check": data["needs_fact_check"], "risk_note": data["risk_note"]}


def to_script(idea: Idea, data: dict) -> Script:
    col = NICHE_COLORS.get(idea.niche, "#8e8d86")
    label = niches().get(idea.niche, {}).get("label", "")
    points = data["points"][:4]
    scenes = [Scene("title", data["hook"], heading=label, big=data["hook_screen"][:18], color=col)]
    for i, p in enumerate(points, 1):
        scenes.append(Scene("focus", p["say"], heading=f"{i}つ目", big=p["head"][:14], color=col,
                            badge=f"{i}/{len(points)}"))
    scenes.append(Scene("cta", data["outro"], heading="あとで見返す用に", big="保存＆フォロー",
                        sub="毎日ためになるショートを投稿中", color=col))
    tags = [t.lstrip("#") for t in data["hashtags"]][:6]
    desc = data["description"].strip() + "\n\n" + " ".join("#" + t for t in tags + ["Shorts"])
    return Script(f"topic:{idea.niche}", scenes, (data["title"][:90] + " #Shorts")[:100], desc[:4900], tags)
