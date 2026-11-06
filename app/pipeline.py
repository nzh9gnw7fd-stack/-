"""収集 → 抽出 → 保存のパイプライン。"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from . import config
from .archetypes import catalog
from .db import session
from .extract import DeckReport, Extraction, MatchRec, llm, rules
from .sources import RawPost, rss, social, x_api

log = logging.getLogger(__name__)


def store_posts(conn: sqlite3.Connection, posts: list[RawPost]) -> int:
    """新規投稿を保存し、構造化済みのものはその場で対戦記録にする。追加件数を返す。"""
    cat = catalog()
    added = 0
    for p in posts:
        cur = conn.execute(
            "INSERT OR IGNORE INTO posts(source, external_id, author, url, text, posted_at) VALUES (?,?,?,?,?,?)",
            (p.source, p.external_id, p.author, p.url, p.text, p.posted_at),
        )
        if not cur.rowcount:
            continue
        added += 1
        if p.structured:
            s = p.structured
            deck = cat.resolve_archetype(s.get("deck"))
            if deck:
                ex = Extraction(
                    matches=[MatchRec(deck, s["result"], cat.resolve_archetype(s.get("opponent")),
                                      cat.resolve_rank(s.get("rank")))],
                    format=s.get("format") or "rotation",
                    extractor="structured",
                )
                _save(conn, cur.lastrowid, p.posted_at, p.author, ex)
    return added


def _save(conn: sqlite3.Connection, post_id: int, ts: str, author: str | None, ex: Extraction) -> None:
    cat = catalog()
    valid = set(cat.archetype_names()) | {f"その他{c}" for c in cat.classes}
    for m in ex.matches:
        if m.deck not in valid or (m.opponent and m.opponent not in valid):
            continue
        conn.execute(
            "INSERT INTO matches(post_id, played_at, author, deck, opponent, result, rank, format, confidence)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (post_id, ts, author, m.deck, m.opponent, m.result, m.rank, ex.format, m.confidence),
        )
    for r in ex.reports:
        if r.deck not in valid:
            continue
        conn.execute(
            "INSERT INTO deck_reports(post_id, reported_at, author, deck, rank, wins, losses, format, confidence)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (post_id, ts, author, r.deck, r.rank, r.wins, r.losses, ex.format, r.confidence),
        )
    conn.execute("UPDATE posts SET extracted = 1, extractor = ? WHERE id = ?", (ex.extractor, post_id))


def extract_pending(conn: sqlite3.Connection, use_llm: bool | None = None, limit: int = 1_000_000) -> dict[str, int]:
    """未処理の投稿を抽出する。LLM が使えればバッチで、ダメならルールベース。"""
    cat = catalog()
    use_llm = llm.available() if use_llm is None else use_llm
    rows = conn.execute(
        "SELECT id, text, posted_at, author FROM posts WHERE extracted = 0 ORDER BY posted_at LIMIT ?", (limit,)
    ).fetchall()
    stats = {"posts": len(rows), "llm": 0, "rules": 0}
    i = 0
    while i < len(rows):
        batch = rows[i : i + (config.LLM_BATCH_SIZE if use_llm else 500)]
        i += len(batch)
        results: list[Extraction] | None = None
        if use_llm:
            results = llm.extract_batch(cat, [r["text"] for r in batch])
            if results is None:
                log.warning("LLM extraction failed for a batch; falling back to rules")
        if results is None:
            results = [rules.extract(cat, r["text"]) for r in batch]
        for row, ex in zip(batch, results):
            _save(conn, row["id"], row["posted_at"], row["author"], ex)
            stats[ex.extractor] = stats.get(ex.extractor, 0) + 1
        conn.commit()
    return stats


# ---- 収集 ----
def _state_get(conn: sqlite3.Connection, key: str) -> str | None:
    conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _state_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO state(key, value) VALUES (?, ?)", (key, value))


def fetch_sources(conn: sqlite3.Connection) -> tuple[list[RawPost], dict[str, int]]:
    """有効な全データ源から新着を取得する（保存はしない）。"""
    posts: list[RawPost] = []
    stats: dict[str, int] = {}
    if x_api.enabled():
        got, newest = x_api.fetch(_state_get(conn, "x_since_id"))
        posts += got
        stats["x"] = len(got)
        if newest:
            _state_set(conn, "x_since_id", newest)
    if config.RSS_FEEDS:
        got = rss.fetch(config.RSS_FEEDS)
        posts += got
        stats["rss"] = len(got)
    if config.SOCIAL_ENABLED:
        for name, got in social.fetch_all(config.sources_config()).items():
            posts += got
            stats[name] = len(got)
    return posts, stats


def collect_once(db_path: Path | None = None) -> dict[str, int]:
    """全ソースから1回収集して抽出まで行う。"""
    with session(db_path) as conn:
        posts, stats = fetch_sources(conn)
        stats["new"] = store_posts(conn, posts)
        conn.commit()
        stats.update({f"extract_{k}": v for k, v in extract_pending(conn).items()})
    return stats
