"""毎日のコンテンツ生成と投稿をまとめて実行する（GitHub Actions の content.yml から呼ばれる）。

1. シャドバWB のデータ動画（独自データなので「量産型」と判定されにくい本命）
   → YouTube ショート / TikTok 下書き / Bluesky・Mastodon・X / ブログ記事 / 週刊レポート
2. 話題ネタ動画（伸びている悩み・関心を Google トレンドと YouTube から拾い、Claude が台本を書く）
   → 既定では YouTube に「非公開」で上げて、人が確認してから公開する（確認待ちキュー）。
     SVWB_TOPIC_AUTOPUBLISH=on かつ AI の自己申告リスクが low・事実確認不要のものだけ自動で公開設定にする。
3. 投稿済み動画の再生数を取り直し、伸びたジャンルの優先度を上げる
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..db import session
from . import blog, digest, settings, trends, video, video_settings, writer, youtube
from . import social as sns
from .tts import TTS

log = logging.getLogger(__name__)
HISTORY = config.ROOT / "content" / "history.json"
IDEAS_DIR = config.ROOT / "content" / "ideas"


def load_history() -> dict:
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"videos": [], "topics": [], "posts": []}


def save_history(h: dict) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    for k in ("videos", "topics", "posts"):
        h[k] = h.get(k, [])[-500:]
    HISTORY.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) if not isinstance(data, str) else data,
                    encoding="utf-8")


def run(out_dir: Path, publish: bool = False, kind: str | None = None, topics: bool = True,
        topic_videos: int = 1, force: bool = False, make_video: bool = True, scale: float = 1.0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    hist = load_history()
    tts = TTS()
    brand = settings().get("brand", "")
    vs = video_settings()
    report: dict = {"published": publish}

    # ---------------------------------------------------------- 1. データ動画
    with session() as c:
        dg = digest.build(c)
    report["digest"] = {"date": dg.date, "days": dg.days, "samples": dg.samples, "publishable": dg.publishable,
                        "reasons": dg.reasons}
    done_today = any(v.get("date") == dg.date and v.get("niche") == "game_svwb" and v.get("id")
                     for v in hist["videos"])
    sc = writer.polish(writer.script(dg, kind, tts.credit))
    d = out_dir / "svwb"
    d.mkdir(exist_ok=True)
    _dump(d / "script.json", sc.to_dict())
    _dump(d / "weekly_report.md", writer.weekly_report(dg))
    meta = {}
    if make_video and (dg.publishable or force):
        if creds := video.attach_media(sc.scenes):
            sc.description += "\n\n映像・写真: " + " / ".join(creds)
        meta = video.render(sc.scenes, d / "short.mp4", tts=tts, scale=scale, brand=brand, bgm=video.pick_bgm())
        report["svwb_video"] = meta
    ok = (dg.publishable or force) and not done_today
    video_url = ""
    if publish and ok and meta and youtube.configured():
        try:
            up = youtube.upload(Path(meta["path"]), sc.title, sc.description, sc.tags, vs["privacy"],
                                vs["category_id"], vs["contains_synthetic_media"], vs.get("playlist_id", ""))
            video_url = up["url"] if up.get("privacy") != "private" else ""
            hist["videos"].append({"date": dg.date, "niche": "game_svwb", "kind": sc.kind, **up, "title": sc.title})
            report["svwb_youtube"] = up
        except Exception as e:  # noqa: BLE001 — 1か所の失敗で全体を止めない
            log.warning("YouTube へのアップロードに失敗: %s", e)
            report["svwb_youtube"] = f"error: {e}"
    texts = writer.sns_posts(dg, video_url)
    _dump(d / "sns.json", texts)
    art = writer.article(dg, sc, video_url)
    _dump(d / "article.json", art)
    if publish and ok:
        img = Path(meta["thumbnail"]) if meta.get("thumbnail") else None
        if img is None and sc.scenes:
            img = video.still(next((s for s in sc.scenes if s.kind == "bars"), sc.scenes[0]), d / "card.png", brand)
        report["svwb_sns"] = sns.publish_all(texts, img, alt=texts["mastodon"][:900],
                                             video=Path(meta["path"]) if meta else None)
        hist["posts"].append({"date": dg.date, **report["svwb_sns"]})
        blog.save(art)
        report["article"] = art["slug"]
    elif publish and not ok:
        report["svwb_skipped"] = "今日は投稿済み" if done_today else "データ不足: " + " / ".join(dg.reasons)

    # ---------------------------------------------------------- 2. 話題ネタ
    if topics:
        ideas, stats = trends.discover(hist)
        md = trends.report_markdown(ideas, stats, dg.date)
        _dump(out_dir / "ideas.md", md)
        _dump(out_dir / "ideas.json", [i.to_dict() for i in ideas])
        IDEAS_DIR.mkdir(parents=True, exist_ok=True)
        _dump(IDEAS_DIR / f"{dg.date}.md", md)
        report["ideas"] = [f"{i.niche}: {i.topic} ({i.score:.2f})" for i in ideas[:10]]
        from . import topic_writer

        if topic_writer.available() and topic_videos > 0:
            made = 0
            for idea in [i for i in ideas if i.niche != "game_svwb"]:
                if made >= topic_videos:
                    break
                res = topic_writer.write(idea, dg.date)
                if not res:
                    continue
                tsc, review = res
                made += 1
                td = out_dir / f"topic{made}"
                td.mkdir(exist_ok=True)
                if tts.credit:
                    tsc.description += f"\n{tts.credit}"
                _dump(td / "script.json", {**tsc.to_dict(), "review": review, "idea": idea.to_dict()})
                if make_video and (creds := video.attach_media(tsc.scenes)):
                    tsc.description += "\n\n映像・写真: " + " / ".join(creds)
                tmeta = video.render(tsc.scenes, td / "short.mp4", tts=tts, scale=scale,
                                     brand=settings().get("topic_brand") or brand, bgm=video.pick_bgm(),
                                     footer="※効果には個人差があります" if review["risk"] != "low" else "") if make_video else {}
                auto = (os.getenv("SVWB_TOPIC_AUTOPUBLISH", "off") == "on" and review["risk"] == "low"
                        and not review["needs_fact_check"])
                entry = {"date": dg.date, "topic": idea.topic, "niche": idea.niche, "review": review, "auto": auto}
                if publish and tmeta and youtube.configured():
                    try:
                        up = youtube.upload(Path(tmeta["path"]), tsc.title, tsc.description, tsc.tags,
                                            vs["privacy"] if auto else "private", "22",
                                            vs["contains_synthetic_media"], channel="topic")
                        entry.update(up)
                        hist["videos"].append({"date": dg.date, "niche": idea.niche, "kind": "topic", **up,
                                               "title": tsc.title})
                        if auto and up.get("privacy") != "private":
                            sns.publish_all({"bluesky": f"{tsc.title}\n{up['url']}", "mastodon": f"{tsc.title}\n{up['url']}",
                                             "x": f"{tsc.title}\n{up['url']}"}, None, "")
                    except Exception as e:  # noqa: BLE001
                        log.warning("話題動画のアップロードに失敗: %s", e)
                        entry["error"] = str(e)
                hist["topics"].append({"date": dg.date, "topic": idea.topic, "niche": idea.niche})
                report.setdefault("topic_videos", []).append(entry)

    # ---------------------------------------------------------- 3. 実績の取り直し
    if publish and youtube.configured():
        try:
            stats_by_id = {s["id"]: s for s in youtube.my_video_stats()}
            if os.getenv("YT_TOPIC_REFRESH_TOKEN"):
                stats_by_id.update({s["id"]: s for s in youtube.my_video_stats(channel="topic")})
            for v in hist["videos"]:
                if (s := stats_by_id.get(v.get("id"))):
                    v["views"], v["likes"] = s["viewCount"], s["likeCount"]
            report["niche_weights"] = trends.performance_weights(hist)
        except Exception as e:  # noqa: BLE001
            log.warning("再生数の取得に失敗: %s", e)
    if publish:
        save_history(hist)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _dump(out_dir / "report.json", report)
    _dump(out_dir / "summary.md", summary_md(report, sc))
    return report


def summary_md(r: dict, sc) -> str:
    """Actions の画面（Job summary）に出す日報。"""
    dg = r["digest"]
    lines = [f"# 自動コンテンツ日報 {dg['date']}", "",
             f"- データ: 直近{dg['days']}日 / 集計対象 {dg['samples']:.0f}件 / 投稿可否: {'OK' if dg['publishable'] else 'NG'}"]
    lines += [f"  - {x}" for x in dg["reasons"]]
    lines.append(f"- データ動画: {sc.title}（{sc.kind}）")
    if isinstance(r.get("svwb_youtube"), dict):
        y = r["svwb_youtube"]
        lines.append(f"  - YouTube: {y['url']}（{y.get('privacy')}）")
    elif r.get("svwb_youtube"):
        lines.append(f"  - YouTube: {r['svwb_youtube']}")
    if r.get("svwb_skipped"):
        lines.append(f"  - 投稿せず: {r['svwb_skipped']}")
    for k, v in (r.get("svwb_sns") or {}).items():
        lines.append(f"  - {k}: {v}")
    if r.get("ideas"):
        lines += ["", "## 今日のネタ候補（上位）", *[f"1. {x}" for x in r["ideas"]]]
    for t in r.get("topic_videos", []):
        status = "自動公開" if t.get("auto") else "確認待ち（YouTube Studio で内容を確認して公開してください）"
        lines.append(f"- 話題動画: {t['topic']} — {t.get('url', '未アップロード')} / {status} / リスク {t['review']['risk']}"
                     + (f"（{t['review']['risk_note']}）" if t['review'].get('risk_note') else ""))
    if r.get("niche_weights"):
        lines += ["", "## ジャンル別の実績補正", *[f"- {k}: ×{v:.2f}" for k, v in r["niche_weights"].items()]]
    return "\n".join(lines) + "\n"
