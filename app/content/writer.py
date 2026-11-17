"""台本・タイトル・概要欄・SNS 文・記事・週刊レポートを書く。

テンプレートだけで動く。言い回しは日付をシードにして毎日変え、
動画の形式も曜日で切り替える（同じ見た目の動画を量産すると YouTube に
「繰り返しの多いコンテンツ」と判断されやすいため）。
SVWB_CONTENT_LLM=on と ANTHROPIC_API_KEY があれば、Claude で台本を自然な言い回しに直す
（数字が変わっていたら採用しない）。
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
from dataclasses import asdict, dataclass, field

from .. import config
from . import settings, site_url
from .digest import Digest

log = logging.getLogger(__name__)

FMT_LABEL = {"rotation": "ローテ", "unlimited": "アンリミ"}
CLASS_COLORS = {
    "エルフ": "#3fb56b", "ロイヤル": "#e0b234", "ウィッチ": "#5b7ff0", "ドラゴン": "#e8743b",
    "ナイトメア": "#a05cd6", "ビショップ": "#d9d4c7", "ネメシス": "#3cc7d6",
}
DEFAULT_COLOR = "#8e8d86"
DISCLAIMER = "※SNSの公開投稿からの推定値です（公式統計ではありません）"

# 曜日（月=0）ごとの動画形式。データが足りなければ ranking に戻す
WEEKLY_PLAN = ["ranking", "trend", "winrate", "matchup", "rank", "ranking", "trend"]


@dataclass
class Scene:
    kind: str                       # title | focus | bars | matchup | cta
    caption: str                    # 読み上げ＆字幕
    heading: str = ""
    big: str = ""
    sub: str = ""
    color: str = DEFAULT_COLOR
    bars: list[list] = field(default_factory=list)   # [ラベル, 0〜1の値, 表示文字列, 色]
    badge: str = ""


@dataclass
class Script:
    kind: str
    scenes: list[Scene]
    title: str
    description: str
    tags: list[str]

    def to_dict(self) -> dict:
        return {**asdict(self)}


def pct(x: float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{x * 100:.{digits}f}%"


def pt(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.1f}pt"


def color(deck: dict | str, cls: str | None = None) -> str:
    if isinstance(deck, dict):
        cls = deck.get("class")
    return CLASS_COLORS.get(cls or "", DEFAULT_COLOR)


def choose_kind(dg: Digest, requested: str | None = None) -> str:
    from datetime import datetime

    kind = requested or WEEKLY_PLAN[datetime.strptime(dg.date, "%Y-%m-%d").weekday()]
    ok = {
        "ranking": len(dg.top()) >= 3,
        "trend": len(dg.risers()) >= 1,
        "winrate": len(dg.strong()) >= 2,
        "matchup": len(dg.notable_matchups()) >= 2,
        "rank": dg.top_rank_meta() is not None,
    }
    return kind if ok.get(kind) else "ranking"


# ---------------------------------------------------------------- 台本
def script(dg: Digest, kind: str | None = None, tts_credit: str = "") -> Script:
    kind = choose_kind(dg, kind)
    rnd = random.Random(f"{dg.date}-{kind}")
    head = f"シャドバWB {dg.date_label} {FMT_LABEL.get(dg.fmt, dg.fmt)}"
    period = f"直近{dg.days}日"
    scenes = {"ranking": _ranking, "trend": _trend, "winrate": _winrate,
              "matchup": _matchup, "rank": _rank}[kind](dg, rnd, head, period)
    scenes.append(_cta(rnd))
    title, desc, tags = _metadata(dg, kind, rnd, tts_credit)
    return Script(kind, scenes, title, desc, tags)


def _bars(decks: list[dict], key: str = "share", fmt=pct) -> list[list]:
    top = max((d[key] or 0) for d in decks) or 1
    return [[d["deck"], (d[key] or 0) / top, fmt(d[key]), color(d)] for d in decks]


def _ranking(dg: Digest, rnd: random.Random, head: str, period: str) -> list[Scene]:
    top = dg.top(5)
    n = len(top)
    hook = rnd.choice([
        f"今いちばん使われているデッキはどれ？{period}の環境トップ{n}！",
        f"シャドバの最新環境、使用率トップ{n}を発表します！",
        f"いま流行っているデッキ、トップ{n}をまとめました！",
    ])
    scenes = [Scene("title", hook, heading=head, big=f"環境TOP{n}", sub=f"使用率ランキング（{period}）")]
    for i in range(n - 1, -1, -1):
        d = top[i]
        trend = d["trend"]
        tr = ("じわじわ増加中" if trend >= 0.02 else "やや減少" if trend <= -0.02 else "横ばい")
        if i == 0:
            cap = rnd.choice([f"そして第1位は、{d['deck']}！使用率は{pct(d['share'])}です。",
                              f"堂々の1位は{d['deck']}。全体の{pct(d['share'])}を占めています。"])
        else:
            cap = rnd.choice([f"第{i + 1}位、{d['deck']}。使用率{pct(d['share'])}、{tr}です。",
                              f"{i + 1}位は{d['deck']}、{pct(d['share'])}。最近は{tr}。"])
        sub = f"使用率 {pct(d['share'])}　直近3日 {pt(trend)}"
        if d["games"] >= 15:
            sub += f"\n推定勝率 {pct(d['winrate'])}"
        scenes.append(Scene("focus", cap, heading=f"第{i + 1}位", big=d["deck"], sub=sub,
                            color=color(d), badge=d.get("class") or ""))
    scenes.append(Scene("bars", rnd.choice(["まとめるとこんな感じです。", "全体を並べるとこうなります。"]),
                        heading=f"使用率TOP{n}（{period}）", bars=_bars(top)))
    return scenes


def _trend(dg: Digest, rnd: random.Random, head: str, period: str) -> list[Scene]:
    up, down = dg.risers(3), dg.fallers(2)
    scenes = [Scene("title", rnd.choice(["今、急に増えているデッキを紹介します！",
                                         "ここ3日で使用率が伸びたデッキはこれ！"]),
                    heading=head, big="急上昇デッキ", sub="直近3日とその前の比較")]
    for i, d in enumerate(up):
        cap = (f"いちばん伸びたのは{d['deck']}。使用率が{pt(d['trend'])}増えて{pct(d['share_recent'])}になりました。"
               if i == 0 else f"続いて{d['deck']}、{pt(d['trend'])}。")
        scenes.append(Scene("focus", cap, heading=f"急上昇 {i + 1}", big=d["deck"],
                            sub=f"{pct(d['share_prior'])} → {pct(d['share_recent'])}（{pt(d['trend'])}）",
                            color=color(d), badge="UP"))
    if down:
        d = down[0]
        scenes.append(Scene("focus", f"逆に減っているのは{d['deck']}。{pt(d['trend'])}です。", heading="減少中",
                            big=d["deck"], sub=f"{pct(d['share_prior'])} → {pct(d['share_recent'])}",
                            color=color(d), badge="DOWN"))
    scenes.append(Scene("bars", "全体の使用率はこちら。", heading=f"使用率（{period}）", bars=_bars(dg.top(5))))
    return scenes


def _winrate(dg: Digest, rnd: random.Random, head: str, period: str) -> list[Scene]:
    best = dg.strong(3)
    scenes = [Scene("title", rnd.choice(["勝てるデッキはどれ？推定勝率のトップを見ていきます。",
                                         "ランクマで勝ちやすいデッキ、データで調べました！"]),
                    heading=head, big="勝率TOP" + str(len(best)), sub=f"推定勝率（{period}）")]
    for i, d in enumerate(best):
        scenes.append(Scene(
            "focus", f"{i + 1}位は{d['deck']}。推定勝率{pct(d['winrate'])}、対戦数はおよそ{d['games']:.0f}戦です。",
            heading=f"勝率 第{i + 1}位", big=d["deck"],
            sub=f"推定勝率 {pct(d['winrate'])}\n95%区間 {pct(d['ci_low'], 0)}〜{pct(d['ci_high'], 0)}",
            color=color(d), badge=d.get("class") or ""))
    scenes.append(Scene("bars", "少ないデータは50%寄りに補正しているので、参考程度にどうぞ。",
                        heading="推定勝率", bars=[[d["deck"], max(0, (d["winrate"] - 0.4) / 0.2), pct(d["winrate"]),
                                                   color(d)] for d in best]))
    return scenes


def _matchup(dg: Digest, rnd: random.Random, head: str, period: str) -> list[Scene]:
    ms = dg.notable_matchups(3)
    cls = {d["deck"]: d.get("class") for d in dg.decks}
    scenes = [Scene("title", rnd.choice(["有利不利がはっきり出ている組み合わせを紹介します！",
                                         "このデッキにはこれが刺さる！相性データです。"]),
                    heading=head, big="相性チェック", sub=f"対戦報告から推定（{period}）")]
    for m in ms:
        scenes.append(Scene(
            "matchup", f"{m['deck']}は{m['opponent']}に対して、推定勝率{pct(m['winrate'])}と有利です。",
            heading="有利な組み合わせ", big=m["deck"], sub=m["opponent"], color=color("", cls.get(m["deck"])),
            bars=[[m["deck"], m["winrate"], pct(m["winrate"]), color("", cls.get(m["deck"]))],
                  [m["opponent"], 1 - m["winrate"], pct(1 - m["winrate"]), color("", cls.get(m["opponent"]))]],
            badge=f"{m['games']:.0f}戦"))
    return scenes


def _rank(dg: Digest, rnd: random.Random, head: str, period: str) -> list[Scene]:
    rank, v = dg.top_rank_meta()
    items = list(v["share"].items())[:5]
    cls = {d["deck"]: d.get("class") for d in dg.decks}
    top = items[0][1] or 1
    scenes = [Scene("title", f"{rank}帯ではどんなデッキが使われているのか、見てみましょう。",
                    heading=head, big=f"{rank}帯の環境", sub=f"上位帯の使用率（{period}）")]
    deck, share = items[0]
    scenes.append(Scene("focus", f"{rank}帯でいちばん多いのは{deck}。{pct(share)}です。", heading=f"{rank}帯 1位",
                        big=deck, sub=f"使用率 {pct(share)}", color=color("", cls.get(deck))))
    scenes.append(Scene("bars", "上位はこんな顔ぶれです。全体のランキングと比べてみてください。",
                        heading=f"{rank}帯 使用率", bars=[[d, s / top, pct(s), color("", cls.get(d))] for d, s in items]))
    return scenes


def _cta(rnd: random.Random) -> Scene:
    return Scene("cta", rnd.choice([
        "毎日自動で更新しています。チャンネル登録で最新の環境をチェック！",
        "詳しいデータはチャンネルのリンクから見られます。フォローよろしくお願いします！",
        "明日も最新の環境をお届けします。チャンネル登録お願いします！",
    ]), heading="毎日更新", big="チャンネル登録", sub="詳しいデータはプロフィールのリンクから")


def _metadata(dg: Digest, kind: str, rnd: random.Random, tts_credit: str) -> tuple[str, str, list[str]]:
    s = settings()
    top = dg.top(5)
    t1 = top[0]["deck"] if top else ""
    titles = {
        "ranking": [f"【シャドバWB】{dg.date_label}環境TOP5！1位は{t1}【使用率】",
                    f"【シャドバWB】今いちばん使われてるデッキは？{dg.date_label}環境ランキング"],
        "trend": [f"【シャドバWB】急上昇デッキ{dg.date_label}｜今増えてるのはこれ",
                  f"【シャドバWB】{dg.date_label} いま伸びてるデッキまとめ"],
        "winrate": [f"【シャドバWB】勝てるデッキはどれ？推定勝率TOP｜{dg.date_label}"],
        "matchup": [f"【シャドバWB】有利不利がはっきり！相性データ｜{dg.date_label}"],
        "rank": [f"【シャドバWB】上位帯の環境はこうなってる｜{dg.date_label}"],
    }
    title = rnd.choice(titles[kind]) + " #Shorts"
    lines = [f"シャドウバース ワールズビヨンドの{FMT_LABEL.get(dg.fmt)}環境（直近{dg.days}日）を、"
             "SNS の公開投稿から自動で集計しています。", ""]
    if top:
        lines.append("■ 使用率TOP5")
        lines += [f"{i + 1}. {d['deck']} {pct(d['share'])}" for i, d in enumerate(top)]
        lines.append("")
    if url := site_url():
        lines += ["▼ 毎日更新の環境データ（使用率・勝率・相性表）", url, ""]
    for a in s.get("affiliate") or []:
        if a.get("url"):
            lines.append(f"【PR】{a['label']} {a['url']}")
    if s.get("affiliate"):
        lines.append("")
    for a in s.get("support_links") or []:
        if a.get("url"):
            lines.append(f"{a['label']} {a['url']}")
    lines += [DISCLAIMER.lstrip("※"), "勝った試合ほど投稿されやすい等の偏りを補正していますが、誤差があります。"]
    if tts_credit:
        lines.append(tts_credit)
    lines.append("")
    tags = list(dict.fromkeys([*s.get("hashtags", []), "シャドバ環境", "Shorts"]))
    lines.append(" ".join("#" + t for t in tags[:8]))
    return title[:100], "\n".join(lines)[:4900], tags + [d["deck"] for d in top[:3]]


# ---------------------------------------------------------------- SNS
def x_weight(text: str) -> int:
    """X の文字数カウント（日本語などは2、URL は23）。"""
    text = re.sub(r"https?://\S+", "x" * 23, text)
    return sum(1 if ord(ch) < 0x1100 else 2 for ch in text)


def sns_posts(dg: Digest, video_url: str = "") -> dict[str, str]:
    top = dg.top(5)
    url = video_url or site_url()
    tags = " ".join("#" + t for t in settings().get("hashtags", [])[:3])
    lines = [f"【シャドバWB 環境速報 {dg.date_label}】", f"{FMT_LABEL.get(dg.fmt)}使用率TOP{len(top)}（直近{dg.days}日・推定）"]
    lines += [f"{i + 1}. {d['deck']} {pct(d['share'])}" for i, d in enumerate(top)]
    if r := dg.risers(1):
        lines.append(f"📈急上昇: {r[0]['deck']}（{pt(r[0]['trend'])}）")
    long_text = "\n".join(lines + ([f"▶ {url}"] if url else []) + [tags])
    # X は短く
    short = lines[:2] + lines[2:5]
    while short and x_weight("\n".join(short + ([url] if url else []) + [tags])) > 280:
        short.pop()
    x_text = "\n".join(short + ([url] if url else []) + [tags])
    return {"bluesky": _clip_graphemes(long_text, 300), "mastodon": long_text[:500], "x": x_text}


def _clip_graphemes(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------- 記事
def article(dg: Digest, sc: Script, video_url: str = "") -> dict:
    """ブログ記事のデータ（HTML は blog.py が広告枠込みで組み立てる）。"""
    top = dg.top(8)
    blocks: list[dict] = [
        {"p": f"{dg.date}時点の『シャドウバース ワールズビヨンド』{FMT_LABEL.get(dg.fmt)}環境を、"
              f"SNS・ブログの公開投稿（直近{dg.days}日・集計対象 約{dg.samples:.0f}件）から推定しました。"},
        {"h2": "使用率ランキング"},
        {"bars": [[d["deck"], d["share"], pct(d["share"]), color(d)] for d in top]},
        {"table": {"head": ["順位", "デッキ", "使用率", "直近3日", "推定勝率"],
                   "rows": [[str(i + 1), d["deck"], pct(d["share"]), pt(d["trend"]),
                             pct(d["winrate"]) if d["games"] >= 15 else "—"] for i, d in enumerate(top)]}},
    ]
    if up := dg.risers(3):
        blocks += [{"h2": "伸びているデッキ"},
                   {"ul": [f"{d['deck']}：{pct(d['share_prior'])} → {pct(d['share_recent'])}（{pt(d['trend'])}）" for d in up]}]
    if down := dg.fallers(3):
        blocks += [{"h2": "減っているデッキ"},
                   {"ul": [f"{d['deck']}：{pct(d['share_prior'])} → {pct(d['share_recent'])}（{pt(d['trend'])}）" for d in down]}]
    if ms := dg.notable_matchups(3):
        blocks += [{"h2": "注目の相性"},
                   {"ul": [f"{m['deck']} → {m['opponent']}：推定勝率 {pct(m['winrate'])}（約{m['games']:.0f}戦）" for m in ms]}]
    if rm := dg.top_rank_meta():
        rank, v = rm
        blocks += [{"h2": f"{rank}帯の使用率"},
                   {"ul": [f"{d}：{pct(s)}" for d, s in list(v["share"].items())[:5]]}]
    if video_url:
        blocks += [{"h2": "動画で見る"}, {"youtube": video_url}]
    blocks += [{"h2": "データについて"},
               {"p": "数値は公開投稿から自動で抽出した推定値です。勝った試合ほど投稿されやすい偏りを、"
                     "対戦を両視点で数える・投稿者ごとの上限・少数サンプルの補正で抑えていますが、公式の統計ではありません。"}]
    title = f"【シャドバWB】{dg.date_label} {FMT_LABEL.get(dg.fmt)}環境まとめ｜使用率1位は{top[0]['deck']}" if top else sc.title
    summary = f"{dg.date}の環境。使用率1位{top[0]['deck']}（{pct(top[0]['share'])}）" if top else ""
    return {"date": dg.date, "slug": f"{dg.date}-{dg.fmt}", "title": title, "summary": summary,
            "blocks": blocks, "kind": sc.kind}


# ---------------------------------------------------------------- 週刊レポート（有料記事の下書き）
def weekly_report(dg: Digest) -> str:
    """note などの有料記事に貼る Markdown。無料部分と有料部分の境目に印を入れる。"""
    out = [f"# シャドバWB 週刊環境レポート（{dg.date}）", "",
           f"集計期間: 直近{dg.days}日 / 集計対象 約{dg.samples:.0f}件 / 勝率に使える対戦 約{dg.games:.0f}戦", "",
           "## 今週のまとめ（無料部分）", ""]
    out += [f"- 使用率1位は **{d['deck']}**（{pct(d['share'])}）" for d in dg.top(1)]
    out += [f"- 急上昇は **{d['deck']}**（{pt(d['trend'])}）" for d in dg.risers(1)]
    out += ["", "---", "", "<!-- ここから下を有料部分にする -->", "", "## 全デッキの使用率と推定勝率", "",
            "| デッキ | クラス | 使用率 | 直近3日 | 推定勝率 | 95%区間 | 対戦数 |", "|---|---|---:|---:|---:|---|---:|"]
    for d in dg.decks:
        out.append(f"| {d['deck']} | {d.get('class') or '—'} | {pct(d['share'])} | {pt(d['trend'])} | "
                   f"{pct(d['winrate'])} | {pct(d['ci_low'], 0)}〜{pct(d['ci_high'], 0)} | {d['games']:.0f} |")
    decks, grid = dg.matchups.get("decks", []), dg.matchups.get("grid", [])
    if decks:
        out += ["", "## 相性表（行のデッキから見た推定勝率）", "", "| | " + " | ".join(decks) + " |",
                "|---" * (len(decks) + 1) + "|"]
        for a, row in zip(decks, grid):
            out.append(f"| {a} | " + " | ".join(pct(c["winrate"], 0) if c else "—" for c in row) + " |")
    if dg.ranks:
        out += ["", "## ランク帯別の使用率", ""]
        for rank, v in dg.ranks.items():
            top = "、".join(f"{d} {pct(s)}" for d, s in list(v["share"].items())[:5])
            out.append(f"- **{rank}**（約{v['samples']:.0f}件）: {top}")
    out += ["", "## 注意", "", DISCLAIMER.lstrip("※")]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- Claude で台本を整える（任意）
def polish(sc: Script) -> Script:
    if os.getenv("SVWB_CONTENT_LLM", "off") != "on":
        return sc
    try:
        import anthropic
    except ImportError:
        return sc
    caps = [s.caption for s in sc.scenes]
    schema = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
              "required": ["lines"], "additionalProperties": False}
    prompt = ("YouTube ショート動画（ゲーム『シャドウバース ワールズビヨンド』の環境データ）のナレーションです。"
              "各行を、テンポよく聞き取りやすい自然な話し言葉に直してください。行数・順番・デッキ名・数字は絶対に変えないこと。"
              "1行40文字以内。誇張や断定（『最強』『必勝』など）は使わない。\n\n"
              + json.dumps(caps, ensure_ascii=False))
    try:
        resp = anthropic.Anthropic().beta.messages.create(
            model=os.getenv("SVWB_CONTENT_MODEL", config.LLM_MODEL), max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason != "end_turn":
            return sc
        lines = json.loads("".join(b.text for b in resp.content if b.type == "text"))["lines"]
    except Exception as e:  # noqa: BLE001 — 失敗したらテンプレートのまま使う
        log.warning("台本の整形をスキップ: %s", e)
        return sc
    if len(lines) != len(caps):
        return sc
    num = re.compile(r"\d+(?:\.\d+)?")
    for s, new in zip(sc.scenes, lines):
        if sorted(num.findall(new)) == sorted(num.findall(s.caption)) and 0 < len(new) <= 60:
            s.caption = new
    return sc
