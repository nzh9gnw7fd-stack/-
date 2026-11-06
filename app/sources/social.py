"""無料で読めるSNSのデータ源。

- Mastodon : GET /api/v1/timelines/tag/{tag}        （認証不要）
- Misskey  : POST /api/notes/search-by-tag           （認証不要）
- Bluesky  : app.bsky.feed.searchPosts               （無料アカウントのアプリパスワード推奨）

投稿者の ID はハッシュ化して保存する（公開リポジトリやサイトに個人のハンドルを並べないため）。
同一人物の判定（1日あたりの寄与上限）には、ハッシュ値でも足りる。
"""
from __future__ import annotations

import hashlib
import html
import logging
import os
import re
from urllib.parse import quote

import httpx

from . import RawPost

log = logging.getLogger(__name__)
TAG = re.compile(r"<[^>]+>")
BR = re.compile(r"<br\s*/?>|</p>\s*<p[^>]*>", re.IGNORECASE)


def anon(source: str, handle: str) -> str:
    return "u_" + hashlib.sha1(f"{source}:{handle}".encode()).hexdigest()[:12]


def strip_html(s: str) -> str:
    return html.unescape(TAG.sub("", BR.sub("\n", s or ""))).strip()


def _iso(s: str) -> str:
    # 2026-11-06T05:40:12.345Z → 2026-11-06T05:40:12Z
    return re.sub(r"\.\d+", "", s).replace("+00:00", "Z")


# ---------- Mastodon ----------
def parse_mastodon(statuses: list[dict], instance: str) -> list[RawPost]:
    out = []
    for st in statuses:
        if st.get("reblog") or st.get("visibility") not in (None, "public", "unlisted"):
            continue
        text = strip_html(st.get("content", ""))
        if not text:
            continue
        acct = st.get("account", {}).get("acct", "?")
        if "@" not in acct:
            acct = f"{acct}@{instance}"
        out.append(RawPost("mastodon", st.get("uri") or st["url"], text, _iso(st["created_at"]),
                           anon("mastodon", acct), st.get("url")))
    return out


def fetch_mastodon(c: httpx.Client, instances: list[str], tags: list[str]) -> list[RawPost]:
    out: list[RawPost] = []
    for inst in instances:
        for tag in tags:
            try:
                r = c.get(f"https://{inst}/api/v1/timelines/tag/{quote(tag)}", params={"limit": 40})
                r.raise_for_status()
                out.extend(parse_mastodon(r.json(), inst))
            except (httpx.HTTPError, ValueError) as e:
                log.warning("mastodon %s #%s failed: %s", inst, tag, e)
    return out


# ---------- Misskey ----------
def parse_misskey(notes: list[dict], instance: str) -> list[RawPost]:
    out = []
    for n in notes:
        text = n.get("text")
        if not text or n.get("visibility") not in (None, "public", "home"):
            continue
        u = n.get("user", {})
        acct = f"{u.get('username', '?')}@{u.get('host') or instance}"
        out.append(RawPost("misskey", f"{instance}:{n['id']}", text.strip(), _iso(n["createdAt"]),
                           anon("misskey", acct), f"https://{instance}/notes/{n['id']}"))
    return out


def fetch_misskey(c: httpx.Client, instances: list[str], tags: list[str]) -> list[RawPost]:
    out: list[RawPost] = []
    for inst in instances:
        for tag in tags:
            try:
                r = c.post(f"https://{inst}/api/notes/search-by-tag", json={"tag": tag, "limit": 50})
                r.raise_for_status()
                out.extend(parse_misskey(r.json(), inst))
            except (httpx.HTTPError, ValueError) as e:
                log.warning("misskey %s #%s failed: %s", inst, tag, e)
    return out


# ---------- Bluesky ----------
def parse_bluesky(posts: list[dict]) -> list[RawPost]:
    out = []
    for p in posts:
        rec = p.get("record", {})
        text = rec.get("text")
        if not text:
            continue
        handle = p.get("author", {}).get("handle", "?")
        rkey = p["uri"].rsplit("/", 1)[-1]
        out.append(RawPost("bluesky", p["uri"], text, _iso(rec.get("createdAt") or p.get("indexedAt")),
                           anon("bluesky", p.get("author", {}).get("did", handle)),
                           f"https://bsky.app/profile/{handle}/post/{rkey}"))
    return out


def fetch_bluesky(c: httpx.Client, queries: list[str]) -> list[RawPost]:
    handle, password = os.getenv("BSKY_HANDLE"), os.getenv("BSKY_APP_PASSWORD")
    base, headers = "https://api.bsky.app", {}
    if handle and password:
        try:
            r = c.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                       json={"identifier": handle, "password": password})
            r.raise_for_status()
            base, headers = "https://bsky.social", {"Authorization": f"Bearer {r.json()['accessJwt']}"}
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("bluesky login failed: %s", e)
    out: list[RawPost] = []
    for q in queries:
        try:
            r = c.get(f"{base}/xrpc/app.bsky.feed.searchPosts",
                      params={"q": q, "limit": 100, "sort": "latest", "lang": "ja"}, headers=headers)
            r.raise_for_status()
            out.extend(parse_bluesky(r.json().get("posts", [])))
        except (httpx.HTTPError, ValueError) as e:
            log.warning("bluesky search %r failed: %s", q, e)
    return out


def fetch_all(cfg: dict) -> dict[str, list[RawPost]]:
    """設定（sources.json）に書かれた全SNSから取得する。"""
    res: dict[str, list[RawPost]] = {}
    with httpx.Client(timeout=20, follow_redirects=True,
                      headers={"User-Agent": cfg.get("user_agent", "svwb-meta")}) as c:
        if (m := cfg.get("mastodon")) and m.get("instances"):
            res["mastodon"] = fetch_mastodon(c, m["instances"], m.get("tags", []))
        if (m := cfg.get("misskey")) and m.get("instances"):
            res["misskey"] = fetch_misskey(c, m["instances"], m.get("tags", []))
        if (b := cfg.get("bluesky")) and b.get("queries"):
            res["bluesky"] = fetch_bluesky(c, b["queries"])
    return res
