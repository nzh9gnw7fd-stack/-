"""投稿のアーカイブ（月ごとの JSONL）。

GitHub Actions での自動更新では、毎回まっさらな環境で動くため、SQLite の代わりに
このテキストファイルをリポジトリにコミットして投稿を蓄積する。実行のたびに
アーカイブから DB を作り直して抽出・集計する（ルール抽出なら数千件で1秒程度）。
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .sources import RawPost


def load(dir_: Path, keep_days: int | None = None) -> list[RawPost]:
    if not dir_.exists():
        return []
    cutoff = None
    if keep_days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[RawPost] = []
    for f in sorted(dir_.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if cutoff and d["posted_at"] < cutoff:
                continue
            out.append(RawPost(**{k: d.get(k) for k in ("source", "external_id", "text", "posted_at", "author", "url")}))
    return out


def append(dir_: Path, posts: list[RawPost], known: set[tuple[str, str]]) -> int:
    """まだアーカイブにない投稿だけを月別ファイルに追記する。"""
    dir_.mkdir(parents=True, exist_ok=True)
    by_month: dict[str, list[str]] = defaultdict(list)
    added = 0
    for p in sorted(posts, key=lambda p: p.posted_at):
        key = (p.source, p.external_id)
        if key in known or p.structured:
            continue
        known.add(key)
        d = {k: v for k, v in asdict(p).items() if k != "structured" and v is not None}
        by_month[p.posted_at[:7]].append(json.dumps(d, ensure_ascii=False))
        added += 1
    for month, lines in by_month.items():
        with open(dir_ / f"{month}.jsonl", "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return added
