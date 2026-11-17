"""SNS への投稿（Bluesky / Mastodon / X）と TikTok への動画送信。

どれも Secrets が無ければ何もしない。
  Bluesky : BSKY_POST_HANDLE / BSKY_POST_APP_PASSWORD（無ければ収集用の BSKY_HANDLE / BSKY_APP_PASSWORD）
  Mastodon: MASTODON_INSTANCE（例 mstdn.jp）/ MASTODON_TOKEN（設定→開発→新規アプリ、write:statuses と write:media）
  X       : X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET（developer.x.com の Free プランで投稿可）
  TikTok  : TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REFRESH_TOKEN（video.upload スコープ）
            審査前のアプリは公開投稿できないので、アプリの「受信箱（下書き）」に送る。
            スマホの TikTok アプリに通知が来るので、音源やキャプションを整えて投稿ボタンを押す。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://[^\s　]+")
TAG_RE = re.compile(r"(?:^|\s)(#[^\s#　]+)")


# ---------------------------------------------------------------- Bluesky
def _bsky_creds() -> tuple[str, str] | None:
    h = os.getenv("BSKY_POST_HANDLE") or os.getenv("BSKY_HANDLE")
    p = os.getenv("BSKY_POST_APP_PASSWORD") or os.getenv("BSKY_APP_PASSWORD")
    return (h, p) if h and p else None


def bsky_facets(text: str) -> list[dict]:
    """リンクとハッシュタグをクリックできるようにする（位置は UTF-8 のバイト単位）。"""
    facets = []
    for m in URL_RE.finditer(text):
        s, e = len(text[: m.start()].encode()), len(text[: m.end()].encode())
        facets.append({"index": {"byteStart": s, "byteEnd": e},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}]})
    for m in TAG_RE.finditer(text):
        tag = m.group(1)
        st = m.start(1)
        s, e = len(text[:st].encode()), len(text[: st + len(tag)].encode())
        facets.append({"index": {"byteStart": s, "byteEnd": e},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag[1:]}]})
    return facets


def post_bluesky(text: str, image: Path | None = None, alt: str = "") -> str | None:
    creds = _bsky_creds()
    if not creds:
        return None
    base = "https://bsky.social/xrpc"
    s = httpx.post(f"{base}/com.atproto.server.createSession",
                   json={"identifier": creds[0], "password": creds[1]}, timeout=30)
    s.raise_for_status()
    sess = s.json()
    h = {"Authorization": f"Bearer {sess['accessJwt']}"}
    record: dict = {"$type": "app.bsky.feed.post", "text": text, "langs": ["ja"],
                    "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    if f := bsky_facets(text):
        record["facets"] = f
    if image and image.exists() and image.stat().st_size < 950_000:
        b = httpx.post(f"{base}/com.atproto.repo.uploadBlob", headers={**h, "Content-Type": "image/png"},
                       content=image.read_bytes(), timeout=60)
        b.raise_for_status()
        record["embed"] = {"$type": "app.bsky.embed.images",
                           "images": [{"alt": alt[:1000], "image": b.json()["blob"],
                                       "aspectRatio": {"width": 9, "height": 16}}]}
    r = httpx.post(f"{base}/com.atproto.repo.createRecord", headers=h, timeout=30,
                   json={"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record})
    r.raise_for_status()
    rkey = r.json()["uri"].rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{sess['handle']}/post/{rkey}"


# ---------------------------------------------------------------- Mastodon
def post_mastodon(text: str, image: Path | None = None, alt: str = "") -> str | None:
    inst, token = os.getenv("MASTODON_INSTANCE"), os.getenv("MASTODON_TOKEN")
    if not (inst and token):
        return None
    base = f"https://{inst.removeprefix('https://').rstrip('/')}"
    h = {"Authorization": f"Bearer {token}"}
    data: dict = {"status": text, "language": "ja", "visibility": "public"}
    if image and image.exists():
        m = httpx.post(f"{base}/api/v2/media", headers=h, timeout=120,
                       files={"file": (image.name, image.read_bytes(), "image/png")}, data={"description": alt[:1500]})
        m.raise_for_status()
        data["media_ids[]"] = m.json()["id"]
    r = httpx.post(f"{base}/api/v1/statuses", headers={**h, "Idempotency-Key": hashlib.sha1(text.encode()).hexdigest()},
                   data=data, timeout=30)
    r.raise_for_status()
    return r.json().get("url")


# ---------------------------------------------------------------- X（OAuth 1.0a ユーザーコンテキスト）
def _pct(s: str) -> str:
    return quote(s, safe="~-._")


def oauth1_header(method: str, url: str, key: str, secret: str, token: str, token_secret: str,
                  params: dict | None = None, nonce: str | None = None, ts: str | None = None) -> str:
    oauth = {"oauth_consumer_key": key, "oauth_nonce": nonce or secrets.token_hex(16),
             "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": ts or str(int(time.time())),
             "oauth_token": token, "oauth_version": "1.0"}
    allp = {**(params or {}), **oauth}
    base_params = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(allp.items()))
    base = "&".join([method.upper(), _pct(url), _pct(base_params)])
    sig = base64.b64encode(hmac.new(f"{_pct(secret)}&{_pct(token_secret)}".encode(), base.encode(),
                                    hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def post_x(text: str) -> str | None:
    keys = [os.getenv(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(keys):
        return None
    url = "https://api.x.com/2/tweets"
    r = httpx.post(url, json={"text": text}, timeout=30,
                   headers={"Authorization": oauth1_header("POST", url, *keys)})  # type: ignore[arg-type]
    r.raise_for_status()
    return f"https://x.com/i/status/{r.json()['data']['id']}"


# ---------------------------------------------------------------- TikTok（受信箱＝下書きへ送る）
def tiktok_upload_draft(video: Path) -> str | None:
    ck, cs, rt = (os.getenv(k) for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"))
    if not (ck and cs and rt):
        return None
    tok = httpx.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=30, data={
        "client_key": ck, "client_secret": cs, "grant_type": "refresh_token", "refresh_token": rt})
    tok.raise_for_status()
    access = tok.json()["access_token"]
    if (new_rt := tok.json().get("refresh_token")) and new_rt != rt:
        log.warning("TikTok のリフレッシュトークンが更新されました。365日以内に TIKTOK_REFRESH_TOKEN を入れ替えてください")
    size = video.stat().st_size
    init = httpx.post("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/", timeout=30,
                      headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json; charset=UTF-8"},
                      json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                            "chunk_size": size, "total_chunk_count": 1}})
    init.raise_for_status()
    data = init.json()["data"]
    put = httpx.put(data["upload_url"], content=video.read_bytes(), timeout=600, headers={
        "Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"})
    put.raise_for_status()
    return data.get("publish_id")


def publish_all(texts: dict[str, str], image: Path | None, alt: str, video: Path | None = None) -> dict:
    """設定済みのところへ全部投稿する。1か所失敗しても他は続ける。"""
    out: dict[str, str | None] = {}
    jobs = [("bluesky", lambda: post_bluesky(texts["bluesky"], image, alt)),
            ("mastodon", lambda: post_mastodon(texts["mastodon"], image, alt)),
            ("x", lambda: post_x(texts["x"]))]
    if video:
        jobs.append(("tiktok_draft", lambda: tiktok_upload_draft(video)))
    for name, fn in jobs:
        try:
            if (res := fn()) is not None:
                out[name] = res
        except httpx.HTTPError as e:
            detail = getattr(getattr(e, "response", None), "text", "")[:300]
            log.warning("%s への投稿に失敗: %s %s", name, e, detail)
            out[name] = f"error: {e}"
    return out
