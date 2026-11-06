"""SQLite ストレージ。

posts   : 収集した生の投稿（ソース・本文・投稿者・日時）
matches : 投稿から抽出した対戦記録（1投稿から複数件ありうる）
decks   : 投稿から抽出した「使用デッキの報告」（勝敗なしの使用率シグナル）
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    author      TEXT,
    url         TEXT,
    text        TEXT NOT NULL,
    posted_at   TEXT NOT NULL,          -- ISO8601 (UTC)
    fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    extracted   INTEGER NOT NULL DEFAULT 0,  -- 0=未処理 1=処理済
    extractor   TEXT,                   -- rules | llm | structured
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_posts_extracted ON posts(extracted);

CREATE TABLE IF NOT EXISTS matches (
    id          INTEGER PRIMARY KEY,
    post_id     INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    played_at   TEXT NOT NULL,
    author      TEXT,
    deck        TEXT NOT NULL,
    opponent    TEXT,                   -- 不明なら NULL（使用率には数え、相性表からは除外）
    result      TEXT NOT NULL CHECK(result IN ('win','loss')),
    rank        TEXT,
    format      TEXT NOT NULL DEFAULT 'rotation',
    confidence  REAL NOT NULL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_matches_time ON matches(played_at);

CREATE TABLE IF NOT EXISTS deck_reports (
    id          INTEGER PRIMARY KEY,
    post_id     INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    reported_at TEXT NOT NULL,
    author      TEXT,
    deck        TEXT NOT NULL,
    rank        TEXT,
    wins        INTEGER,                -- 「マスター到達 15勝5敗」等の集計報告
    losses      INTEGER,
    format      TEXT NOT NULL DEFAULT 'rotation',
    confidence  REAL NOT NULL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_reports_time ON deck_reports(reported_at);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: Path | None = None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
