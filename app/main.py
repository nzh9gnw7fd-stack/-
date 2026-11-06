"""Web API とダッシュボード配信。

起動: uvicorn app.main:app --reload
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import aggregate as agg
from . import config, pipeline
from .archetypes import catalog
from .db import session
from .extract import llm
from .sources import manual, rss, x_api

log = logging.getLogger("svwb")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _poller():
    """X / RSS が設定されていれば定期的に収集する。"""
    while True:
        try:
            if x_api.enabled() or config.RSS_FEEDS:
                stats = await asyncio.to_thread(pipeline.collect_once)
                log.info("collected: %s", stats)
        except Exception:  # 収集の失敗でサーバーを落とさない
            log.exception("collect failed")
        await asyncio.sleep(config.POLL_MINUTES * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_poller())
    yield
    task.cancel()


app = FastAPI(title="SVWB Meta Tracker", lifespan=lifespan)


def _filters(fmt: str, ranks: str | None, days: int, min_conf: float) -> agg.Filters:
    return agg.Filters(
        format=fmt,
        ranks=[r for r in ranks.split(",") if r] if ranks else None,
        days=days,
        min_conf=min_conf,
    )


Fmt = Query("rotation", pattern="^(rotation|unlimited)$")
Ranks = Query(None, description="カンマ区切り。例: マスター,グランドマスター")
Days = Query(14, ge=1, le=120)
MinConf = Query(0.5, ge=0, le=1)


@app.get("/api/meta")
def meta():
    cat = catalog()
    return {
        "classes": list(cat.classes),
        "ranks": cat.ranks,
        "archetypes": [{"name": a.name, "class": a.cls} for a in cat.archetypes],
        "sources": {"x": x_api.enabled(), "rss": len(config.RSS_FEEDS), "llm": llm.available()},
        "poll_minutes": config.POLL_MINUTES,
    }


@app.get("/api/summary")
def summary(format: str = Fmt, ranks: str | None = Ranks, days: int = Days, min_conf: float = MinConf):
    with session() as c:
        return agg.summary(c, _filters(format, ranks, days, min_conf))


@app.get("/api/decks")
def decks(format: str = Fmt, ranks: str | None = Ranks, days: int = Days, min_conf: float = MinConf):
    with session() as c:
        return agg.deck_stats(c, _filters(format, ranks, days, min_conf))


@app.get("/api/shares")
def shares(format: str = Fmt, ranks: str | None = Ranks, days: int = Days, min_conf: float = MinConf):
    with session() as c:
        return agg.share_timeseries(c, _filters(format, ranks, days, min_conf))


@app.get("/api/ranks")
def ranks_(format: str = Fmt, days: int = Days, min_conf: float = MinConf):
    with session() as c:
        return agg.rank_breakdown(c, _filters(format, None, days, min_conf))


@app.get("/api/matchups")
def matchups(format: str = Fmt, ranks: str | None = Ranks, days: int = Days, min_conf: float = MinConf,
             top: int = Query(10, ge=2, le=30)):
    with session() as c:
        return agg.matchups(c, _filters(format, ranks, days, min_conf), top)


@app.get("/api/posts")
def posts(limit: int = Query(50, le=500), deck: str | None = None):
    """最近の投稿と抽出結果（抽出が正しいか目視確認するため）。"""
    with session() as c:
        sql = "SELECT * FROM posts"
        args: list = []
        if deck:
            sql += (" WHERE id IN (SELECT post_id FROM matches WHERE deck=? OR opponent=?"
                    " UNION SELECT post_id FROM deck_reports WHERE deck=?)")
            args = [deck, deck, deck]
        rows = c.execute(sql + " ORDER BY posted_at DESC LIMIT ?", [*args, limit]).fetchall()
        out = []
        for r in rows:
            ms = c.execute("SELECT deck, opponent, result, rank, confidence FROM matches WHERE post_id=?", (r["id"],))
            rs = c.execute("SELECT deck, rank, wins, losses, confidence FROM deck_reports WHERE post_id=?", (r["id"],))
            out.append({**dict(r), "matches": [dict(m) for m in ms], "reports": [dict(x) for x in rs]})
        return out


class ImportBody(BaseModel):
    kind: Literal["text", "csv", "json", "rss"]
    content: str
    author: str | None = None


@app.post("/api/import")
def import_(body: ImportBody):
    try:
        if body.kind == "text":
            items = manual.from_text(body.content, body.author)
        elif body.kind == "csv":
            items = manual.from_csv(body.content)
        elif body.kind == "json":
            items = manual.from_json(body.content)
        else:
            items = rss.fetch([u.strip() for u in body.content.split() if u.strip()])
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"読み込めませんでした: {e}") from e
    with session() as c:
        added = pipeline.store_posts(c, items)
        c.commit()
        stats = pipeline.extract_pending(c)
    return {"received": len(items), "added": added, "extract": stats}


@app.post("/api/collect")
def collect():
    return pipeline.collect_once()


STATIC = config.ROOT / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
