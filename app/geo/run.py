"""世界地理チャンネル: 次のテーマを選ぶ → 資料集め → 台本 → 動画 → YouTube（geo.yml から週2回）。

台本は Claude（ANTHROPIC_API_KEY）が必須。完成した動画は既定で「非公開」でアップロードし、
内容を確認してから公開する（SVWB_GEO_PRIVACY=public で最初から公開）。
自分で用意した素材（Google Earth Studio の書き出しなど）は episodes/assets/<slug>/ に置くと優先して使う。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..content import youtube
from ..content.tts import TTS
from ..content.video import pick_bgm
from . import build, research, script

log = logging.getLogger(__name__)
TOPICS = config.ROOT / "geo_topics.json"
HISTORY = config.ROOT / "content" / "geo_history.json"


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def next_topic(name: str | None = None) -> dict | None:
    cfg = _load(TOPICS, {"topics": []})
    done = {e["topic"] for e in _load(HISTORY, {"episodes": []})["episodes"] if e.get("video_id")}
    for t in cfg["topics"]:
        if (name and t["name"] == name) or (not name and t["name"] not in done):
            return t
    return None


def run(out_dir: Path, publish: bool = False, topic_name: str | None = None, episode_file: Path | None = None,
        w: int = 1920, h: int = 1080) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = _load(TOPICS, {})
    channel = cfg.get("channel", {})
    rep: dict = {"started": datetime.now(timezone.utc).isoformat()}
    if episode_file:
        ep = json.loads(episode_file.read_text(encoding="utf-8"))
        topic = {"name": ep["place"]["name"]}
    else:
        topic = next_topic(topic_name)
        if not topic:
            rep["error"] = "作るテーマがありません。geo_topics.json に追加してください"
            return rep
        if not script.available():
            rep["error"] = "台本づくりに ANTHROPIC_API_KEY が必要です"
            return rep
        res = research.gather(topic)
        if res.get("lat") is None:
            rep["error"] = f"{topic['name']} の座標が Wikipedia から取れませんでした（geo_topics.json に lat/lon を書いてください）"
            return rep
        ep = script.write(topic, res)
        if not ep:
            rep["error"] = "台本の生成に失敗しました"
            return rep
    (out_dir / "script.json").write_text(json.dumps(ep, ensure_ascii=False, indent=1), encoding="utf-8")
    tts = TTS(speaker=int(channel.get("narration_speaker", 13)), speed=float(os.getenv("SVWB_GEO_SPEED", "1.1")))
    folder = config.ROOT / "episodes" / "assets" / ep["slug"]
    meta = build.build(ep, out_dir, w, h, 24, tts=tts, bgm=pick_bgm(), folder=folder)
    if channel.get("name"):
        meta["description"] = meta["description"].replace("\n■ 目次", f"\n{channel['name']}\n\n■ 目次", 1)
    rep.update({"topic": topic["name"], "title": ep["title"], "minutes": meta["minutes"], "review": ep.get("review", "")})
    if publish and youtube.configured("geo"):
        privacy = os.getenv("SVWB_GEO_PRIVACY", "private")
        try:
            up = youtube.upload(Path(meta["path"]), ep["title"], meta["description"], ep.get("tags", []), privacy,
                                "27", False, os.getenv("SVWB_GEO_PLAYLIST", ""), channel="geo")
            youtube.set_thumbnail(up["id"], Path(meta["thumbnail"]), channel="geo")
            rep["youtube"] = up
            hist = _load(HISTORY, {"episodes": []})
            hist["episodes"].append({"date": datetime.now(timezone.utc).date().isoformat(), "topic": topic["name"],
                                     "title": ep["title"], "video_id": up["id"], "url": up["url"],
                                     "privacy": up.get("privacy"), "minutes": meta["minutes"]})
            HISTORY.parent.mkdir(parents=True, exist_ok=True)
            HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            log.warning("アップロードに失敗: %s", e)
            rep["youtube"] = f"error: {e}"
    # 縦型の予告ショート（本編へ誘導）
    if os.getenv("SVWB_GEO_TEASER", "on") == "on":
        try:
            vurl = rep["youtube"]["url"].replace("/shorts/", "/watch?v=") if isinstance(rep.get("youtube"), dict) else ""
            t = build.teaser(ep, out_dir, tts, vurl, pick_bgm())
            rep["teaser"] = {"path": t["path"], "duration": t["duration"]}
            if publish and youtube.configured("geo") and isinstance(rep.get("youtube"), dict):
                up = youtube.upload(Path(t["path"]), t["title"], t["description"], ep.get("tags", []),
                                    os.getenv("SVWB_GEO_PRIVACY", "private"), "27", False, channel="geo")
                rep["teaser"]["youtube"] = up
        except Exception as e:  # noqa: BLE001
            log.warning("予告ショートの作成に失敗: %s", e)
    lines = [f"# 世界地理チャンネル {topic['name']}", "", f"- タイトル: {ep['title']}", f"- 長さ: {meta['minutes']} 分"]
    if isinstance(rep.get("youtube"), dict):
        lines.append(f"- YouTube: {rep['youtube']['url']}（{rep['youtube'].get('privacy')}）")
    if isinstance(rep.get("teaser", {}).get("youtube"), dict):
        lines.append(f"- 予告ショート: {rep['teaser']['youtube']['url']}")
    if ep.get("review"):
        lines.append(f"- 事実確認してほしい所（AI の自己申告）: {ep['review']}")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep
