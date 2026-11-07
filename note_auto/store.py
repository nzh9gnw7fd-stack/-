"""テーマ一覧と、生成済み記事・投稿履歴の保存。"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .generate import Article, Topic
from .render import article_markdown


def load_topics(path: Path | None = None) -> list[Topic]:
    path = path or config.TOPICS_PATH
    if not path.exists():
        example = config.ROOT / "topics.example.json"
        raise FileNotFoundError(f"{path} がありません。{example} をコピーして作ってください")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Topic.from_dict(d) for d in data]


def load_state() -> dict[str, Any]:
    if config.STATE_PATH.exists():
        return json.loads(config.STATE_PATH.read_text(encoding="utf-8"))
    return {"articles": {}, "posts": []}


def save_state(state: dict[str, Any]) -> None:
    config.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def article_path(topic_id: str) -> Path:
    return config.OUT_DIR / topic_id / "article.json"


def save_article(a: Article) -> Path:
    p = article_path(a.topic_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(a.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (p.parent / "preview.md").write_text(
        article_markdown(a.title, a.free_body, a.paid_body, a.price, a.hashtags), encoding="utf-8"
    )
    state = load_state()
    state["articles"][a.topic_id] = {"title": a.title, "status": a.status, "score": a.review.get("score")}
    save_state(state)
    return p


def load_article(topic_id: str) -> Article:
    return Article.from_dict(json.loads(article_path(topic_id).read_text(encoding="utf-8")))


def pending_topics(topics: list[Topic]) -> list[Topic]:
    done = load_state()["articles"]
    return [t for t in topics if t.id not in done]


def articles_with_status(status: str) -> list[str]:
    return [k for k, v in load_state()["articles"].items() if v.get("status") == status]


def posts_today(today: date | None = None) -> int:
    today = today or datetime.now(timezone.utc).astimezone().date()
    return sum(1 for p in load_state()["posts"] if p.get("date") == today.isoformat() and p.get("published"))


def record_post(a: Article, url: str, published: bool) -> None:
    state = load_state()
    now = datetime.now(timezone.utc).astimezone()
    state["posts"].append(
        {"topic_id": a.topic_id, "title": a.title, "url": url, "published": published,
         "price": a.price, "date": now.date().isoformat(), "at": now.isoformat(timespec="seconds")}
    )
    state["articles"].setdefault(a.topic_id, {})["status"] = "posted" if published else "drafted"
    state["articles"][a.topic_id]["url"] = url
    save_state(state)
    a.status = "posted" if published else "drafted"
    p = article_path(a.topic_id)
    if p.exists():
        p.write_text(json.dumps(a.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def set_status(topic_id: str, status: str) -> None:
    a = load_article(topic_id)
    a.status = status
    save_article(a)
