"""手動インポート。

1. テキスト貼り付け: 投稿本文を1件ずつ（空行2つ以上 or "---" 区切り）
2. CSV: 対戦ログ・大会結果などの構造化データ
   列: played_at, deck, opponent, result(win/loss), rank, author, format
3. JSON: [{"text": ..., "author": ..., "posted_at": ..., "url": ...}, ...]
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone

from . import RawPost


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hid(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode()).hexdigest()[:16]


def from_text(blob: str, author: str | None = None, posted_at: str | None = None) -> list[RawPost]:
    chunks = [c.strip() for c in re.split(r"\n\s*(?:---+)\s*\n|\n{3,}", blob) if c.strip()]
    ts = posted_at or _now()
    return [RawPost("manual", _hid(c, author or ""), c, ts, author) for c in chunks]


def from_json(blob: str) -> list[RawPost]:
    items = json.loads(blob)
    out = []
    for it in items:
        text = it["text"]
        out.append(
            RawPost(
                source=it.get("source", "manual"),
                external_id=str(it.get("id") or _hid(text, it.get("author", ""))),
                text=text,
                posted_at=it.get("posted_at") or _now(),
                author=it.get("author"),
                url=it.get("url"),
            )
        )
    return out


def from_csv(blob: str) -> list[RawPost]:
    out = []
    for i, row in enumerate(csv.DictReader(io.StringIO(blob))):
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if not row.get("deck") or row.get("result") not in ("win", "loss"):
            continue
        ts = row.get("played_at") or _now()
        text = f"{row['deck']} vs {row.get('opponent') or '?'} {row['result']}"
        out.append(
            RawPost(
                source="structured",
                external_id=_hid(ts, text, row.get("author", ""), str(i)),
                text=text,
                posted_at=ts,
                author=row.get("author") or None,
                structured=row,
            )
        )
    return out
