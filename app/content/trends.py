"""伸びやすい話題を探して点数を付ける。

データ源（どれも公式・無料。スクレイピングはしない）:
  1. Google トレンド「急上昇ワード」RSS（日本）……いま検索が急増している言葉
  2. YouTube Data API（YT_API_KEY）
     - 急上昇（mostPopular, 日本）……今バズっている動画のタイトル傾向
     - ジャンルの検索語ごとに、直近7日のショートを再生数順で取得し、
       「登録者数の割に再生されている」（＝話題の力で伸びた）動画を見つける
  3. 自分のチャンネルの実績（content/history.json）……伸びたジャンルの重みを上げる

X と TikTok のトレンドは公式の無料 API が無いので使っていない（規約違反のスクレイピングはしない）。
点数 = 伸び（再生数/登録者数・再生速度・検索量）× 悩みワードとの一致 × ジャンルの重み × 新しさ
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import statistics
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import httpx

from .. import config

log = logging.getLogger(__name__)
YT = "https://www.googleapis.com/youtube/v3"
TRENDS_RSS = "https://trends.google.com/trending/rss?geo=JP"
UA = {"User-Agent": "Mozilla/5.0 (compatible; trend-digest/1.0)"}


@lru_cache(maxsize=1)
def topics_config() -> dict:
    try:
        return json.loads((config.ROOT / "topics.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"niches": {}, "pain_words": [], "hooks": []}


def niches() -> dict[str, dict]:
    return {k: v for k, v in topics_config().get("niches", {}).items() if v.get("enabled", True)}


@dataclass
class Evidence:
    source: str
    title: str
    url: str = ""
    views: int = 0
    subs: int = 0
    hours: float = 0.0
    traffic: int = 0

    @property
    def outlier(self) -> float:
        return self.views / max(self.subs, 1000)

    @property
    def velocity(self) -> float:
        return self.views / max(self.hours, 1.0)


@dataclass
class Idea:
    niche: str
    topic: str
    score: float
    pains: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score"] = round(self.score, 3)
        return d


# ---------------------------------------------------------------- 収集
def google_trends(client: httpx.Client) -> list[Evidence]:
    try:
        r = client.get(TRENDS_RSS, headers=UA, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (httpx.HTTPError, ET.ParseError) as e:
        log.warning("Google トレンドを取得できません: %s", e)
        return []
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        traffic = item.findtext("ht:approx_traffic", default="", namespaces=ns)
        news = [n.findtext("ht:news_item_title", default="", namespaces=ns) for n in item.findall("ht:news_item", ns)]
        num = int(re.sub(r"\D", "", traffic) or 0)
        out.append(Evidence("google_trends", title + (f"（{news[0]}）" if news and news[0] else ""),
                            item.findtext("link") or "", traffic=num))
    return out


def _yt_get(client: httpx.Client, path: str, **params) -> dict:
    r = client.get(f"{YT}/{path}", params={**params, "key": os.environ["YT_API_KEY"]}, timeout=30)
    r.raise_for_status()
    return r.json()


def _hours_since(ts: str) -> float:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return max(1.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)


def _with_stats(client: httpx.Client, ids: list[str]) -> list[Evidence]:
    if not ids:
        return []
    vids = _yt_get(client, "videos", part="snippet,statistics,contentDetails", id=",".join(ids[:50]))["items"]
    ch_ids = list({v["snippet"]["channelId"] for v in vids})
    subs = {}
    for i in range(0, len(ch_ids), 50):
        for c in _yt_get(client, "channels", part="statistics", id=",".join(ch_ids[i:i + 50]))["items"]:
            subs[c["id"]] = int(c["statistics"].get("subscriberCount", 0) or 0)
    return [Evidence("youtube", v["snippet"]["title"], f"https://youtube.com/watch?v={v['id']}",
                     views=int(v["statistics"].get("viewCount", 0)), subs=subs.get(v["snippet"]["channelId"], 0),
                     hours=_hours_since(v["snippet"]["publishedAt"])) for v in vids]


def youtube_popular(client: httpx.Client) -> list[Evidence]:
    """急上昇（1ユニット）。"""
    data = _yt_get(client, "videos", part="id", chart="mostPopular", regionCode="JP", maxResults=50)
    return _with_stats(client, [v["id"] for v in data.get("items", [])])


def youtube_search(client: httpx.Client, query: str, days: int = 7) -> list[Evidence]:
    """直近のショートを再生数順に（search は1回100ユニット。1日の上限は10000）。"""
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _yt_get(client, "search", part="id", q=query, type="video", videoDuration="short", order="viewCount",
                   regionCode="JP", relevanceLanguage="ja", publishedAfter=after, maxResults=15)
    return _with_stats(client, [i["id"]["videoId"] for i in data.get("items", []) if i["id"].get("videoId")])


# ---------------------------------------------------------------- 採点
def pains_in(text: str, niche: dict | None = None) -> list[str]:
    words = list(topics_config().get("pain_words", [])) + list((niche or {}).get("pains", []))
    return sorted({w for w in words if w and w in text})


def classify(text: str) -> str | None:
    """どのジャンルの話か（seeds と pains の一致数で判定）。"""
    best, score = None, 0
    for key, n in niches().items():
        s = sum(2 for seed in n.get("seeds", []) for w in seed.split() if w in text)
        s += sum(1 for p in n.get("pains", []) if p in text)
        if s > score:
            best, score = key, s
    return best


def _clean(title: str) -> str:
    t = re.sub(r"#\S+", "", title)
    t = re.sub(r"[【\[].*?[】\]]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:60]


def score_ideas(by_seed: dict[tuple[str, str], list[Evidence]], trends: list[Evidence],
                popular: list[Evidence], history: dict | None = None, perf: dict[str, float] | None = None,
                top: int = 15) -> list[Idea]:
    history = history or {}
    used = {str(v.get("topic", "")) for v in history.get("topics", [])[-60:]}
    perf = perf or {}
    ideas: list[Idea] = []
    ns = niches()
    for (niche_key, seed), evs in by_seed.items():
        n = ns.get(niche_key, {})
        evs = [e for e in evs if e.views > 0]
        if not evs:
            continue
        evs.sort(key=lambda e: -e.outlier)
        med_outlier = statistics.median(e.outlier for e in evs[:8])
        med_vel = statistics.median(e.velocity for e in evs[:8])
        # 伸びている動画のタイトルに出てくる悩みワード
        pains = sorted({p for e in evs[:8] for p in pains_in(e.title, n)})
        momentum = math.log10(1 + med_outlier * 10) + 0.5 * math.log10(1 + med_vel)
        s = momentum * (1 + 0.25 * min(len(pains), 4)) * n.get("weight", 1.0) * perf.get(niche_key, 1.0)
        if seed in used:
            s *= 0.5
        ideas.append(Idea(niche_key, seed, s, pains, evs[:5]))
    # Google トレンド・急上昇から、ジャンルに当てはまるものを追加（時事ネタ）
    for e in trends + popular:
        key = classify(e.title)
        if not key:
            continue
        n = ns[key]
        pains = pains_in(e.title, n)
        base = math.log10(1 + e.traffic) if e.traffic else math.log10(1 + e.velocity)
        s = 0.6 * base * (1 + 0.25 * len(pains)) * n.get("weight", 1.0) * perf.get(key, 1.0)
        topic = _clean(e.title)
        if topic and topic not in used:
            ideas.append(Idea(key, topic, s, pains, [e]))
    ideas.sort(key=lambda i: -i.score)
    # 同じジャンルばかりにならないよう、各ジャンル最大3件
    out, per = [], {}
    for i in ideas:
        if per.get(i.niche, 0) < 3:
            out.append(i)
            per[i.niche] = per.get(i.niche, 0) + 1
        if len(out) >= top:
            break
    return out


def performance_weights(history: dict) -> dict[str, float]:
    """自分の動画の再生数から、ジャンルごとの重み（0.6〜1.6）を出す。"""
    views: dict[str, list[int]] = {}
    for v in history.get("videos", []):
        if v.get("niche") and isinstance(v.get("views"), int):
            views.setdefault(v["niche"], []).append(v["views"])
    if len(views) < 2:
        return {}
    med = {k: statistics.median(v) for k, v in views.items() if len(v) >= 2}
    if not med:
        return {}
    overall = statistics.median(med.values()) or 1
    return {k: max(0.6, min(1.6, (m / overall) ** 0.5)) for k, m in med.items()}


def discover(history: dict | None = None, max_searches: int | None = None) -> tuple[list[Idea], dict]:
    """ネタ候補と、収集の内訳を返す。YT_API_KEY が無ければ Google トレンドだけで判定する。"""
    history = history or {}
    max_searches = max_searches or int(os.getenv("SVWB_TREND_SEARCHES", "12"))
    stats: dict[str, int] = {}
    with httpx.Client(follow_redirects=True) as client:
        trends = google_trends(client)
        stats["google_trends"] = len(trends)
        popular: list[Evidence] = []
        by_seed: dict[tuple[str, str], list[Evidence]] = {}
        if os.getenv("YT_API_KEY"):
            try:
                popular = youtube_popular(client)
            except httpx.HTTPError as e:
                log.warning("YouTube 急上昇を取得できません: %s", e)
            # ジャンルの重みが高い順に、検索語を少しずつ回す（日付でずらして毎日違う語を調べる）
            seeds = [(k, s) for k, n in sorted(niches().items(), key=lambda kv: -kv[1].get("weight", 1))
                     if k != "game_svwb" for s in n.get("seeds", [])]
            if seeds:
                off = datetime.now().toordinal() % len(seeds)
                seeds = (seeds[off:] + seeds[:off])[:max_searches]
            for key, seed in seeds:
                try:
                    by_seed[(key, seed)] = youtube_search(client, seed)
                except httpx.HTTPError as e:
                    log.warning("YouTube 検索に失敗（%s）: %s", seed, e)
                    break  # クォータ切れのことが多いので打ち切る
        stats["youtube_popular"] = len(popular)
        stats["youtube_searches"] = len(by_seed)
    ideas = score_ideas(by_seed, trends, popular, history, performance_weights(history))
    return ideas, stats


def report_markdown(ideas: list[Idea], stats: dict, date: str) -> str:
    """人が読む「今日のネタ候補」レポート。"""
    ns = niches()
    out = [f"# 今日のネタ候補（{date}）", "",
           f"収集: Google トレンド {stats.get('google_trends', 0)}件 / YouTube 急上昇 {stats.get('youtube_popular', 0)}本 / "
           f"YouTube 検索 {stats.get('youtube_searches', 0)}語", "",
           "| # | ジャンル | ネタ | 点数 | 刺さっている悩み・関心 |", "|---:|---|---|---:|---|"]
    for i, idea in enumerate(ideas, 1):
        out.append(f"| {i} | {ns.get(idea.niche, {}).get('label', idea.niche)} | {idea.topic} | {idea.score:.2f} | "
                   f"{'、'.join(idea.pains) or '—'} |")
    out += ["", "## 根拠（伸びている動画・検索）", ""]
    for idea in ideas[:8]:
        out.append(f"### {idea.topic}")
        for e in idea.evidence[:3]:
            if e.source == "youtube":
                out.append(f"- [{e.title}]({e.url}) — {e.views:,}回 / 登録者{e.subs:,}人（{e.outlier:.1f}倍）")
            else:
                out.append(f"- {e.title}（検索 {e.traffic:,}+）")
        out.append("")
    return "\n".join(out)
