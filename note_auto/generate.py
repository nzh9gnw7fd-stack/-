"""Claude で記事を書き、別の呼び出しで品質チェックする。

1. write(): テーマから「無料部分」「有料部分」「価格」「ハッシュタグ」「X 用の告知文」を構造化出力で作る
2. review(): 読者目線の採点（具体性、無料部分の価値、価格に見合う量、誇大表現がないか）
3. 合格点に届かなければ、指摘を渡して1回だけ書き直す。それでも不合格なら needs_review にして投稿しない
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from . import config

log = logging.getLogger(__name__)


@dataclass
class Topic:
    id: str
    theme: str
    reader: str = ""            # 想定読者（誰のどんな悩みか）
    angle: str = ""             # 切り口・独自の経験や材料
    price: int | None = None    # 指定がなければ Claude に提案させる
    notes: str = ""             # 入れてほしい事実・データ・体験談など

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Topic":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Article:
    topic_id: str
    title: str
    free_body: str              # Markdown。無料で読める部分（ここで買うか決まる）
    paid_body: str              # Markdown。有料ラインより下
    price: int
    hashtags: list[str]
    promo_post: str             # X などでの告知文（140字程度）
    review: dict[str, Any] = field(default_factory=dict)
    status: str = "draft"       # draft / approved / needs_review / posted

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Article":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


WRITER_SYSTEM = """あなたは note で有料記事を書くプロの書き手です。読者が「お金を払ってよかった」と思える記事を書きます。

方針:
- 無料部分（free_body）: 誰のどんな悩みを解決するか、読むと何ができるようになるか、有料部分の目次、
  書き手がこのテーマを語れる理由を書く。無料部分だけでも読む価値がある具体的な情報を1つは入れる。
  最後は有料部分へ自然につなげる。
- 有料部分（paid_body）: 手順・テンプレート・チェックリスト・具体例・失敗例など、そのまま使える中身を書く。
  抽象論や一般論で水増ししない。価格に見合う分量と密度にする。
- 見出しは Markdown の ## と ### を使う。箇条書き、太字、引用（>）も使ってよい。表は使わない（note で崩れる）。
- 文体はです・ます調。一文を短く。

守ること（守らないと note の規約・景品表示法・アカウント停止のリスクがある）:
- 「誰でも月100万」「絶対稼げる」など、根拠のない収益の約束や誇大表現をしない。
- 書き手のプロフィールやテーマのメモにない体験・実績・数字を作らない。一般的な情報は一般論として書く。
- 統計や事実を書くときは、確かなものだけにする。不確かなら書かない。
- 医療・法律・投資の個別助言はしない。
- 他人の文章をそのまま写さない。"""

REVIEWER_SYSTEM = """あなたは note の有料記事を買う側の、厳しめの読者兼編集者です。
記事を読み、次の観点で採点してください（合計100点）。

- 具体性・実用性（30点）: 有料部分はそのまま使える手順・例・テンプレートか。一般論の水増しがないか。
- 無料部分の質（20点）: 誰向けで何が得られるかが明確で、無料部分だけでも価値があるか。
- 価格との釣り合い（20点）: 分量と密度が価格に見合うか。
- 正確さ・誠実さ（20点）: 誇大表現、根拠のない収益の約束、プロフィールにない体験や実績の捏造、怪しい数字がないか。
  1つでもあれば safe を false にする。
- 読みやすさ（10点）: 構成、見出し、文の短さ。

issues には具体的な直し方を書く。"""


def _article_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "32字前後。読者と得られる結果が分かるタイトル"},
            "free_body": {"type": "string", "description": "無料部分（Markdown）"},
            "paid_body": {"type": "string", "description": "有料部分（Markdown）"},
            "price": {"type": "integer", "description": f"円。{config.MIN_PRICE}〜{config.MAX_PRICE}"},
            "hashtags": {"type": "array", "items": {"type": "string"}, "description": "# を付けない。3〜6個"},
            "promo_post": {"type": "string", "description": "X 用の告知文。130字以内。URL は入れない"},
        },
        "required": ["title", "free_body", "paid_body", "price", "hashtags", "promo_post"],
        "additionalProperties": False,
    }


def _review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "safe": {"type": "boolean", "description": "誇大表現・捏造・規約違反のおそれがなければ true"},
            "issues": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        "required": ["score", "safe", "issues", "summary"],
        "additionalProperties": False,
    }


def _client():
    import anthropic

    return anthropic.Anthropic()


def _call_json(system: list[dict], user: str, schema: dict, effort: str) -> dict[str, Any]:
    """構造化出力で JSON を返す。長文になるのでストリーミングで受け取る。"""
    with _client().beta.messages.stream(
        model=config.MODEL,
        max_tokens=64000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        # 安全分類器による誤拒否のときはサーバー側で別モデルに再実行させる
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        resp = stream.get_final_message()

    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Claude が生成を断りました: {getattr(resp, 'stop_details', None)}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("出力が長すぎて途中で切れました")
    text = "".join(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def _profile() -> str:
    p = config.PROFILE_PATH
    return p.read_text(encoding="utf-8").strip() if p.exists() else "（プロフィール未設定。体験談や実績は書かないこと）"


def _system(base: str) -> list[dict]:
    # 書き手プロフィールは毎回同じなのでキャッシュを効かせる
    return [
        {"type": "text", "text": base},
        {"type": "text", "text": f"書き手のプロフィール:\n{_profile()}", "cache_control": {"type": "ephemeral"}},
    ]


def _topic_prompt(t: Topic) -> str:
    lines = [f"テーマ: {t.theme}"]
    if t.reader:
        lines.append(f"想定読者: {t.reader}")
    if t.angle:
        lines.append(f"切り口: {t.angle}")
    if t.notes:
        lines.append(f"使ってよい材料・メモ:\n{t.notes}")
    lines.append(f"価格: {t.price}円で書く" if t.price else "価格: 内容に見合う額を提案する（迷ったら300〜980円）")
    return "\n".join(lines)


def clamp_price(p: Any) -> int:
    try:
        p = int(p)
    except (TypeError, ValueError):
        p = 500
    return max(config.MIN_PRICE, min(config.MAX_PRICE, p))


def clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = t.strip().lstrip("#＃").replace(" ", "")
        if t and t not in out:
            out.append(t)
    return out[:6]


def write(t: Topic, feedback: list[str] | None = None, previous: Article | None = None) -> Article:
    user = "次のテーマで note の有料記事を書いてください。\n\n" + _topic_prompt(t)
    if feedback and previous:
        user += (
            "\n\n前回の原稿は編集者から次の指摘を受けました。すべて直した原稿を書き直してください。\n"
            + "\n".join(f"- {x}" for x in feedback)
            + f"\n\n<previous_title>{previous.title}</previous_title>\n"
            f"<previous_free>\n{previous.free_body}\n</previous_free>\n<previous_paid>\n{previous.paid_body}\n</previous_paid>"
        )
    d = _call_json(_system(WRITER_SYSTEM), user, _article_schema(), config.EFFORT)
    return Article(
        topic_id=t.id,
        title=d["title"].strip(),
        free_body=d["free_body"].strip(),
        paid_body=d["paid_body"].strip(),
        price=clamp_price(t.price or d["price"]),
        hashtags=clean_tags(d["hashtags"]),
        promo_post=d["promo_post"].strip(),
    )


def review(t: Topic, a: Article) -> dict[str, Any]:
    user = (
        f"{_topic_prompt(t)}\n\n価格: {a.price}円\n\n<title>{a.title}</title>\n"
        f"<free_part>\n{a.free_body}\n</free_part>\n<paid_part>\n{a.paid_body}\n</paid_part>"
    )
    return _call_json(_system(REVIEWER_SYSTEM), user, _review_schema(), config.REVIEW_EFFORT)


def passed(r: dict[str, Any]) -> bool:
    return bool(r.get("safe")) and int(r.get("score", 0)) >= config.PASS_SCORE


def create(t: Topic) -> Article:
    """書く → 採点 → 必要なら書き直す。"""
    a = write(t)
    for attempt in range(config.MAX_REWRITES + 1):
        r = review(t, a)
        a.review = r
        log.info("review %s: score=%s safe=%s", t.id, r.get("score"), r.get("safe"))
        if passed(r):
            a.status = "approved"
            return a
        if attempt < config.MAX_REWRITES:
            a = write(t, feedback=r.get("issues", []), previous=a)
    a.status = "needs_review"
    return a
