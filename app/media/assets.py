"""商用利用できる写真・映像を探してダウンロードする。

  Wikimedia Commons : キー不要。CC0 / パブリックドメイン / CC BY / CC BY-SA のみ採用（クレジット必須のものは概要欄に自動記載）
  Pexels            : PEXELS_API_KEY（無料）。写真・映像とも商用可・クレジット不要（礼儀として記載）
  Pixabay           : PIXABAY_API_KEY（無料）。同上

他人の YouTube 動画やテレビ映像を切り抜いて使うことはしない（著作権侵害になり、チャンネル停止の原因になる）。
"""
from __future__ import annotations

import hashlib
import html
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from .. import config

log = logging.getLogger(__name__)
CACHE = Path(os.getenv("SVWB_MEDIA_CACHE", config.DATA_DIR / "media_cache"))
UA = {"User-Agent": "geo-explainer-video-bot/0.2 (https://github.com/"
                    + os.getenv("GITHUB_REPOSITORY", "") + ") python-httpx"}
OK_LICENSES = re.compile(r"^(cc0|public domain|pd|cc[- ]by(-sa)?[- ]?\d|cc[- ]by(-sa)?$|attribution)", re.I)
NG_LICENSES = re.compile(r"\bnc\b|\bnd\b|non-?commercial|fair use|gfdl only", re.I)


@dataclass
class Asset:
    kind: str            # image | video
    url: str
    source: str          # commons | pexels | pixabay | eox | nasa | local
    credit: str = ""     # 作者
    license: str = ""
    page: str = ""       # 元ページ
    title: str = ""
    path: str = ""       # ダウンロード先
    width: int = 0
    height: int = 0

    @property
    def attribution(self) -> str:
        parts = [p for p in (self.title, self.credit, self.license, self.page) if p]
        return " / ".join(parts)

    def to_dict(self) -> dict:
        return asdict(self)


_last_call = [0.0]


def _polite_get(c: httpx.Client, url: str, params: dict, tries: int = 5) -> httpx.Response:
    """Wikimedia の API 利用ルールに合わせて、間隔を空けて1件ずつ、429 なら待って再試行する。"""
    import time

    for i in range(tries):
        wait = 1.0 - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        r = c.get(url, params=params)
        if r.status_code != 429:
            r.raise_for_status()
            return r
        time.sleep(min(30, float(r.headers.get("retry-after", 0) or 0) or 2 ** (i + 1)))
    r.raise_for_status()
    return r


def _relevant(query: str, text: str) -> bool:
    """Commons の検索はゆるい（"smartphone bill" で大統領の写真が出る）ので、
    検索語の 2/3 以上がファイル名か説明に含まれるものだけ使う。"""
    import math

    words = [w for w in re.findall(r"[\w']+", query.lower()) if len(w) > 2]
    if not words:
        return True
    t = text.lower()
    hit = sum(1 for w in words if w in t or (w.endswith("s") and w[:-1] in t))
    return hit >= math.ceil(len(words) * 2 / 3)


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()[:120]


# ---------------------------------------------------------------- Wikimedia Commons
def commons(query: str, kind: str = "image", n: int = 6, client: httpx.Client | None = None) -> list[Asset]:
    c = client or httpx.Client(headers=UA, timeout=30, follow_redirects=True)
    flt = "filetype:video" if kind == "video" else "filetype:bitmap"
    try:
        r = _polite_get(c, "https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"{query} {flt}", "gsrlimit": max(n * 3, 10), "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1920})
        pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Commons 検索に失敗（%s）: %s", query, e)
        return []
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = _strip(meta.get("LicenseShortName", {}).get("value", ""))
        if not lic or NG_LICENSES.search(lic) or not OK_LICENSES.search(lic):
            continue
        if not _relevant(query, p.get("title", "") + " " + _strip(meta.get("ImageDescription", {}).get("value", ""))[:200]):
            continue
        mime = ii.get("mime", "")
        if kind == "image" and not mime.startswith("image/"):
            continue
        if kind == "image" and min(ii.get("width", 0), ii.get("height", 0)) < 700:
            continue
        if kind == "video" and not mime.startswith("video/"):
            continue
        url = ii.get("thumburl") if kind == "image" and ii.get("thumburl") else ii.get("url")
        if kind == "image" and url and "/thumb/" not in url:
            continue  # 原寸しか無いもの（=小さい画像）は使わない（原寸の連続取得は 429 になる）
        out.append(Asset(kind, url, "commons", _strip(meta.get("Artist", {}).get("value", "")) or "Unknown", lic,
                         ii.get("descriptionurl", ""), p.get("title", "").removeprefix("File:"),
                         width=ii.get("width", 0), height=ii.get("height", 0)))
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- Pexels / Pixabay（キーがあれば）
def pexels(query: str, kind: str = "video", n: int = 6, orientation: str = "landscape") -> list[Asset]:
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return []
    url = "https://api.pexels.com/videos/search" if kind == "video" else "https://api.pexels.com/v1/search"
    try:
        r = httpx.get(url, params={"query": query, "per_page": n, "orientation": orientation},
                      headers={"Authorization": key}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Pexels 検索に失敗（%s）: %s", query, e)
        return []
    out = []
    if kind == "video":
        for v in data.get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
            if not files:
                continue
            want = 1920 if orientation == "landscape" else 1080
            f = min(files, key=lambda f: abs(max(f["width"], f["height"]) - want * (16 / 9 if orientation != "landscape" else 1)))
            out.append(Asset("video", f["link"], "pexels", v.get("user", {}).get("name", ""), "Pexels License",
                             v.get("url", ""), width=f["width"], height=f["height"]))
    else:
        for p in data.get("photos", []):
            out.append(Asset("image", p["src"]["large2x"], "pexels", p.get("photographer", ""), "Pexels License",
                             p.get("url", ""), p.get("alt", ""), width=p.get("width", 0), height=p.get("height", 0)))
    return out


def pixabay(query: str, kind: str = "video", n: int = 6) -> list[Asset]:
    key = os.getenv("PIXABAY_API_KEY")
    if not key:
        return []
    url = "https://pixabay.com/api/videos/" if kind == "video" else "https://pixabay.com/api/"
    try:
        r = httpx.get(url, params={"key": key, "q": query, "per_page": max(n, 3), "safesearch": "true"}, timeout=30)
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Pixabay 検索に失敗（%s）: %s", query, e)
        return []
    out = []
    for h in hits[:n]:
        if kind == "video":
            v = h.get("videos", {}).get("large") or h.get("videos", {}).get("medium")
            if v and v.get("url"):
                out.append(Asset("video", v["url"], "pixabay", h.get("user", ""), "Pixabay Content License",
                                 h.get("pageURL", ""), width=v.get("width", 0), height=v.get("height", 0)))
        else:
            out.append(Asset("image", h.get("largeImageURL", ""), "pixabay", h.get("user", ""),
                             "Pixabay Content License", h.get("pageURL", ""), h.get("tags", "")))
    return out


def find(query: str, kind: str = "video", n: int = 3, orientation: str = "landscape",
         exclude: set[str] | None = None) -> list[Asset]:
    """映像を優先して探し、無ければ写真にする。exclude は使用済み URL（同じ素材の連続使用を避ける）。"""
    exclude = exclude or set()
    found: list[Asset] = []
    # Commons の映像は記録映像が中心で一般的な場面には合わないので、横長（地理の長尺）だけで使う
    videos = [("video", pexels), ("video", pixabay)] + ([("video", commons)] if orientation == "landscape" else [])
    order = (videos if kind == "video" else []) + \
            [("image", pexels), ("image", pixabay), ("image", commons)]
    for k, fn in order:
        res = fn(query, k, n * 2, orientation) if fn is pexels else fn(query, k, n * 2)
        found += [a for a in res if a.url not in exclude and a.url not in {f.url for f in found}]
        if len(found) >= n:
            break
    return found[:n]


def download(a: Asset, max_mb: int = 80) -> Asset | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    ext = Path(a.url.split("?")[0]).suffix.lower() or (".mp4" if a.kind == "video" else ".jpg")
    path = CACHE / (hashlib.sha1(a.url.encode()).hexdigest()[:16] + ext)
    if not path.exists():
        if "wikimedia.org" in a.url:  # Wikimedia は 1 秒に 1 件まで
            import time

            wait = 1.0 - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
        try:
            with httpx.stream("GET", a.url, headers=UA, timeout=120, follow_redirects=True) as r:
                r.raise_for_status()
                size = 0
                with path.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 16):
                        size += len(chunk)
                        if size > max_mb * 1e6:
                            raise ValueError("ファイルが大きすぎます")
                        f.write(chunk)
        except (httpx.HTTPError, ValueError, OSError) as e:
            log.warning("素材のダウンロードに失敗: %s %s", a.url, e)
            path.unlink(missing_ok=True)
            return None
    a.path = str(path)
    return a


def local(folder: Path) -> list[Asset]:
    """自分で用意した素材（例: Google Earth Studio で書き出した映像）をそのまま使う。"""
    if not folder.exists():
        return []
    out = []
    for p in sorted(folder.iterdir()):
        k = "video" if p.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv") else "image" if p.suffix.lower() in (
            ".jpg", ".jpeg", ".png", ".webp") else ""
        if k:
            credit = "Google Earth" if "earth" in p.stem.lower() else ""
            out.append(Asset(k, p.as_uri(), "local", credit, "", "", p.stem, str(p)))
    return out
