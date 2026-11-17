"""Wikipedia（日本語・英語）から、台本の裏付けになる事実情報と座標を集める。

Claude には「この資料に書かれていることを中心に話す」よう指示し、作り話（ハルシネーション）を減らす。
本文はそのまま読み上げず、要約・言い換えて使う（参考資料として概要欄にリンクを載せる）。
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from ..media.assets import UA, _polite_get

log = logging.getLogger(__name__)


def page(lang: str, title: str, max_chars: int = 14000) -> dict:
    if not title:
        return {}
    try:
        with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as c:
            r = _polite_get(c, f"https://{lang}.wikipedia.org/w/api.php", {
                "action": "query", "format": "json", "redirects": 1, "titles": title,
                "prop": "extracts|coordinates|info", "explaintext": 1, "exsectionformat": "plain", "inprop": "url"})
        pages = list(r.json().get("query", {}).get("pages", {}).values())
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Wikipedia（%s:%s）を取得できません: %s", lang, title, e)
        return {}
    if not pages or "missing" in pages[0]:
        return {}
    p = pages[0]
    coords = (p.get("coordinates") or [{}])[0]
    text = p.get("extract", "")
    # 参考文献・脚注などの末尾は落とす
    for cut in ("脚注", "参考文献", "関連項目", "外部リンク", "References", "See also", "External links", "Notes"):
        i = text.find("\n" + cut + "\n")
        if i > 0:
            text = text[:i]
    return {"title": p.get("title"), "url": p.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{quote(title)}",
            "lat": coords.get("lat"), "lon": coords.get("lon"), "text": text[:max_chars]}


def gather(topic: dict) -> dict:
    ja = page("ja", topic.get("wiki_ja", ""), 12000)
    en = page("en", topic.get("wiki_en", ""), 16000)
    lat = topic.get("lat") or en.get("lat") or ja.get("lat")
    lon = topic.get("lon") or en.get("lon") or ja.get("lon")
    return {"ja": ja, "en": en, "lat": lat, "lon": lon,
            "sources": [x["url"] for x in (ja, en) if x.get("url")]}
