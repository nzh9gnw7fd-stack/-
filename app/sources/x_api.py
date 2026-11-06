"""X (Twitter) API v2 の recent search。

利用には有料プラン（Basic 以上）の Bearer Token が必要。環境変数 X_BEARER_TOKEN を
設定すると有効になる。スクレイピングは利用規約違反なので実装しない。
since_id を保存して、前回以降の投稿だけを取得する。
"""
from __future__ import annotations

import logging

import httpx

from .. import config
from . import RawPost

log = logging.getLogger(__name__)
URL = "https://api.x.com/2/tweets/search/recent"


def enabled() -> bool:
    return bool(config.X_BEARER_TOKEN)


def fetch(since_id: str | None = None, max_pages: int = 5) -> tuple[list[RawPost], str | None]:
    """(投稿, 最新の since_id) を返す。"""
    if not enabled():
        return [], since_id
    params = {
        "query": config.X_QUERY,
        "max_results": 100,
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    if since_id:
        params["since_id"] = since_id
    headers = {"Authorization": f"Bearer {config.X_BEARER_TOKEN}"}
    out: list[RawPost] = []
    newest = since_id
    with httpx.Client(timeout=30, headers=headers) as c:
        for _ in range(max_pages):
            try:
                r = c.get(URL, params=params)
            except httpx.HTTPError as e:
                log.warning("X API request failed: %s", e)
                break
            if r.status_code == 429:
                log.warning("X API rate limited")
                break
            if r.status_code != 200:
                log.warning("X API %s: %s", r.status_code, r.text[:200])
                break
            data = r.json()
            users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
            for t in data.get("data", []):
                user = users.get(t["author_id"], t["author_id"])
                out.append(
                    RawPost("x", t["id"], t["text"], t["created_at"].replace(".000Z", "Z"),
                            f"@{user}", f"https://x.com/{user}/status/{t['id']}")
                )
            meta = data.get("meta", {})
            if meta.get("newest_id") and (newest is None or int(meta["newest_id"]) > int(newest)):
                newest = meta["newest_id"]
            if not meta.get("next_token"):
                break
            params["next_token"] = meta["next_token"]
    return out, newest
