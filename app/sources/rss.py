"""RSS / Atom フィードの取得（攻略ブログ、note、YouTube チャンネルの新着など）。"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx

from . import RawPost

log = logging.getLogger(__name__)
ATOM = "{http://www.w3.org/2005/Atom}"
TAG = re.compile(r"<[^>]+>")


def _iso(s: str | None) -> str:
    if not s:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(xml: str, feed_url: str) -> list[RawPost]:
    root = ET.fromstring(xml)
    out: list[RawPost] = []
    for item in root.iter("item"):  # RSS 2.0
        title = item.findtext("title") or ""
        desc = TAG.sub("", item.findtext("description") or "")
        link = item.findtext("link")
        out.append(
            RawPost("rss", item.findtext("guid") or link or title, f"{title}\n{desc}".strip(),
                    _iso(item.findtext("pubDate")), item.findtext("author") or feed_url, link)
        )
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        title = entry.findtext(f"{ATOM}title") or ""
        summary = TAG.sub("", entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content") or "")
        link_el = entry.find(f"{ATOM}link")
        link = link_el.get("href") if link_el is not None else None
        author = entry.findtext(f"{ATOM}author/{ATOM}name") or feed_url
        out.append(
            RawPost("rss", entry.findtext(f"{ATOM}id") or link or title, f"{title}\n{summary}".strip(),
                    _iso(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")), author, link)
        )
    return out


def fetch(feeds: list[str]) -> list[RawPost]:
    out: list[RawPost] = []
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "svwb-meta/0.1"}) as c:
        for url in feeds:
            try:
                r = c.get(url)
                r.raise_for_status()
                out.extend(parse(r.text, url))
            except (httpx.HTTPError, ET.ParseError) as e:
                log.warning("RSS fetch failed %s: %s", url, e)
    return out
