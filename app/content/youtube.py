"""YouTube Data API v3 で動画をアップロードする。

必要なもの（GitHub の Secrets）:
  YT_CLIENT_ID / YT_CLIENT_SECRET : Google Cloud Console で作る OAuth クライアント（種類「デスクトップアプリ」）
  YT_REFRESH_TOKEN                : `python cli.py youtube-auth` を自分の PC で1回実行して取得

注意:
- API の審査（監査）を受けていないプロジェクトからのアップロードは、自動で「非公開」に固定される。
  公開で投稿するには Google の「YouTube API Services - Audit and Quota Extension」フォームで審査を受ける。
- 1回のアップロードで 1600 ユニット消費（既定の上限は 1日 10000 ユニット＝約6本）。
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

log = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"


def configured() -> bool:
    return all(os.getenv(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def access_token(channel: str = "main") -> str:
    """channel="topic" なら話題ネタ用チャンネルのトークン（YT_TOPIC_REFRESH_TOKEN、無ければメインと同じ）。"""
    rt = (os.getenv("YT_TOPIC_REFRESH_TOKEN") if channel == "topic" else None) or os.environ["YT_REFRESH_TOKEN"]
    r = httpx.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": rt, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def upload(path: Path, title: str, description: str, tags: list[str], privacy: str = "private",
           category_id: str = "20", synthetic: bool = False, playlist_id: str = "", channel: str = "main") -> dict:
    token = access_token(channel)
    size = path.stat().st_size
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": _tags(tags),
                    "categoryId": category_id, "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": bool(synthetic), "embeddable": True},
    }
    h = {"Authorization": f"Bearer {token}"}
    init = httpx.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={**h, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                      content=json.dumps(body), timeout=60)
    init.raise_for_status()
    loc = init.headers["Location"]
    with path.open("rb") as f:
        r = httpx.put(loc, headers={**h, "Content-Type": "video/mp4", "Content-Length": str(size)},
                      content=f.read(), timeout=600)
    r.raise_for_status()
    video = r.json()
    vid = video["id"]
    status = video.get("status", {})
    if privacy == "public" and status.get("privacyStatus") == "private":
        log.warning("公開を指定しましたが非公開になりました。API プロジェクトの審査が必要です")
    if playlist_id:
        try:
            httpx.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=h, timeout=30, json={
                "snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": vid}}
            }).raise_for_status()
        except httpx.HTTPError as e:
            log.warning("再生リストへの追加に失敗: %s", e)
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}", "privacy": status.get("privacyStatus")}


def _tags(tags: list[str]) -> list[str]:
    out, total = [], 0
    for t in dict.fromkeys(t.strip().lstrip("#") for t in tags if t.strip()):
        if total + len(t) + 2 > 480:
            break
        out.append(t)
        total += len(t) + 2
    return out


# ---------------------------------------------------------------- 初回だけ: リフレッシュトークンを取る
def authorize(client_id: str, client_secret: str, port: int = 8765) -> str:
    """自分の PC で実行する。ブラウザで許可すると refresh token を表示する。"""
    redirect = f"http://127.0.0.1:{port}/"
    state = secrets.token_urlsafe(16)
    url = AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state})
    got: dict[str, str] = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                got["code"] = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("認証が終わりました。このタブは閉じて構いません。".encode())

        def log_message(self, *a):
            pass

    print("ブラウザで次の URL を開いて、動画を投稿するチャンネルのアカウントで許可してください:\n" + url)
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    srv = HTTPServer(("127.0.0.1", port), H)
    while "code" not in got:
        srv.handle_request()
    r = httpx.post(TOKEN_URL, data={"code": got["code"], "client_id": client_id, "client_secret": client_secret,
                                    "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    return r.json()["refresh_token"]


# ---------------------------------------------------------------- 分析（伸びた動画の傾向を次に活かす）
def my_video_stats(max_results: int = 50, channel: str = "main") -> list[dict]:
    """自分のチャンネルの最近の動画の再生数・高評価・コメント数。"""
    h = {"Authorization": f"Bearer {access_token(channel)}"}
    ch = httpx.get(f"{API}/channels", params={"part": "contentDetails", "mine": "true"}, headers=h, timeout=30)
    ch.raise_for_status()
    items = ch.json().get("items", [])
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = httpx.get(f"{API}/playlistItems", params={"part": "contentDetails", "playlistId": uploads,
                                                   "maxResults": max_results}, headers=h, timeout=30)
    pl.raise_for_status()
    ids = [i["contentDetails"]["videoId"] for i in pl.json().get("items", [])]
    if not ids:
        return []
    v = httpx.get(f"{API}/videos", params={"part": "snippet,statistics", "id": ",".join(ids)}, headers=h, timeout=30)
    v.raise_for_status()
    return [{"id": i["id"], "title": i["snippet"]["title"], "published": i["snippet"]["publishedAt"],
             **{k: int(i["statistics"].get(k, 0)) for k in ("viewCount", "likeCount", "commentCount")}}
            for i in v.json().get("items", [])]
