"""台本（episodes/*.json と同じ形式）から、長尺動画・サムネイル・概要欄を作る。

映像の種類（segment.visual.type）:
  earth : 地球儀から目的地へズーム（Google Earth 風。衛星画像は NASA / Sentinel-2）
  photo : 写真・映像（Pexels / Pixabay の映像を優先、無ければ Wikimedia Commons の写真をゆっくり動かす）
  video : photo と同じだが映像をより優先
  term  : 地理用語のカード（背景は現地の衛星画像をぼかしたもの）
  map   : 衛星画像の静止画をゆっくり動かす
"""
from __future__ import annotations

import json
import logging

from pathlib import Path

from PIL import Image, ImageDraw

from ..content.tts import TTS, split_sentences
from ..content.video import Fonts
from ..media import assets, compose, geo

log = logging.getLogger(__name__)


class Credits:
    def __init__(self):
        self.items: dict[str, str] = {}

    def add(self, key: str, text: str) -> None:
        if text and key not in self.items:
            self.items[key] = text


def _query_variants(q: str, place: dict) -> list[str]:
    out = [q]
    if place.get("name_en") and place["name_en"].lower() not in q.lower():
        out.append(f"{place['name_en']} {q}")
    words = q.split()
    if len(words) > 2:
        out.append(" ".join(words[:2]))
    return out


def plan_shots(ep: dict, w: int, h: int, fps: int, credits: Credits, folder: Path | None = None) -> list[compose.Shot]:
    place = ep["place"]
    painter = compose.Painter(w, h)
    fonts = Fonts(w / 1920)
    used: set[str] = set()
    local = assets.local(folder) if folder else []   # 自分で置いた素材（Google Earth Studio の書き出しなど）
    bg_cache: dict = {}

    def place_bg() -> Image.Image:
        if "bg" not in bg_cache:
            bg_cache["bg"] = geo.blurred(geo.still(place["lat"], place["lon"], 10, w, h))
            credits.add("s2", geo.CREDITS["s2"])
        return bg_cache["bg"]

    shots: list[compose.Shot] = []
    last_earth: tuple[float, float] | None = None
    for ci, ch in enumerate(ep["chapters"]):
        for si, seg in enumerate(ch["segments"]):
            v = seg.get("visual", {"type": "map"})
            sentences = split_sentences(seg["text"])
            title = ch["title"] if si == 0 else ""
            kind = v.get("type", "map")
            shot = compose.Shot(source=lambda: compose.Solid(Image.new("RGB", (w, h))), sentences=sentences, title=title)

            if kind == "earth":
                lat, lon, zoom = float(v["lat"]), float(v["lon"]), float(v.get("zoom", 10))
                start = last_earth if v.get("start_from_previous") and last_earth else None
                label = v.get("label", "")
                mine = next((a for a in local if a.kind == "video" and a.title.lower().startswith(f"earth_{ci}_{si}")), None)
                if mine:  # Google Earth Studio の書き出しがあれば優先
                    shot.source = (lambda p=mine.path: compose.VideoClip(p, w, h, fps, start=0))
                    shot.credit = "Google Earth"
                    credits.add("google_earth", "地図映像: Google Earth")
                else:
                    holder: dict = {}

                    def mk(lat=lat, lon=lon, zoom=zoom, label=label, start=start, holder=holder):
                        z = geo.EarthZoom(lat, lon, zoom, holder["shot"].duration, w, h, label=label,
                                          start_lat=start[0] if start else None, start_lon=start[1] if start else None)
                        holder["z"] = z

                        class S(compose.Source):
                            def frame(self, t):
                                return z.frame(t)
                        return S()

                    def ov(img, t, sh, holder=holder):
                        return geo.draw_hud(img, holder["z"].hud(t), fonts) if "z" in holder else img

                    shot.source, shot.overlay = mk, ov
                    holder["shot"] = shot
                    shot.credit = "NASA Blue Marble / Sentinel-2 cloudless 2016 by EOX"
                    credits.add("bluemarble", geo.CREDITS["bluemarble"])
                    if zoom > 5.5:
                        credits.add("s2", geo.CREDITS["s2"])
                    shot.min_duration = 9.0
                last_earth = (lat, lon)

            elif kind == "term":
                term, reading, desc = v.get("term", ""), v.get("reading", ""), v.get("desc", "")
                shot.source = lambda: compose.KenBurns(place_bg(), w, h, 12, seed=len(term))

                def ov(img, t, sh, term=term, reading=reading, desc=desc):
                    painter.term_card(img, term, reading, desc, min(1.0, t / 0.4))
                    return img
                shot.overlay = ov
                shot.credit = "背景: Sentinel-2 cloudless 2016 by EOX"

            elif kind == "map":
                lat, lon, zoom = float(v.get("lat", place["lat"])), float(v.get("lon", place["lon"])), float(v.get("zoom", 10))
                img_holder = {}

                def mk_map(lat=lat, lon=lon, zoom=zoom, holder=img_holder, shot=shot):
                    return compose.KenBurns(geo.still(lat, lon, zoom, int(w * 1.2), int(h * 1.2)), w, h,
                                            shot.duration, seed=int(lat * 100))
                shot.source = mk_map
                shot.credit = "衛星画像: Sentinel-2 cloudless 2016 by EOX"
                credits.add("s2", geo.CREDITS["s2"])

            else:  # photo / video
                want = "video" if kind in ("video", "photo") else "image"
                found: list[assets.Asset] = []
                for q in _query_variants(v.get("query", place.get("name_en", place["name"])), place):
                    found = assets.find(q, want, n=2, exclude=used)
                    if found:
                        break
                a = None
                for cand in found:
                    a = assets.download(cand)
                    if a:
                        break
                if a:
                    used.add(a.url)
                    if a.kind == "video":
                        shot.source = (lambda p=a.path: compose.VideoClip(p, w, h, fps))
                    else:
                        im = Image.open(a.path)
                        shot.source = (lambda im=im, shot=shot, seed=len(used): compose.KenBurns(im, w, h, shot.duration, seed))
                    who = a.credit if a.source != "commons" else f"{a.credit} / {a.license}"
                    shot.credit = f"{'映像' if a.kind == 'video' else '写真'}: {who} ({a.source})"
                    credits.add(a.url, f"{a.title or v.get('query', '')} — {a.credit}, {a.license}, {a.page}".strip(" ,—"))
                else:  # 見つからなければ衛星画像で代用
                    shot.source = (lambda shot=shot: compose.KenBurns(
                        geo.still(place["lat"], place["lon"], 11, int(w * 1.2), int(h * 1.2)), w, h, shot.duration))
                    shot.credit = "衛星画像: Sentinel-2 cloudless 2016 by EOX"
                    credits.add("s2", geo.CREDITS["s2"])
            shots.append(shot)
    return shots


def thumbnail(ep: dict, out: Path, w: int = 1280, h: int = 720) -> Path:
    place = ep["place"]
    bg = geo.still(place["lat"], place["lon"], float(ep.get("thumbnail_zoom", 10.5)), w, h)
    bg = Image.eval(bg, lambda v: int(min(255, v * 1.1)))
    img = bg.convert("RGBA")
    shade = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(shade)
    for x in range(w):
        d.line([(x, 0), (x, h)], fill=(0, 0, 0, int(200 * max(0, 1 - x / (w * 0.75)))))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    F = Fonts(w / 1280)
    lines = ep.get("thumbnail_text", ep["title"][:16]).split("\n")
    f = F(120 if max(len(x) for x in lines) <= 6 else 96)
    y = h * 0.5 - (len(lines) * f.size * 1.15) / 2
    for i, ln in enumerate(lines):
        d.text((60, y + i * f.size * 1.15), ln, font=f, fill=(255, 230, 0) if i == 0 else (255, 255, 255),
               stroke_width=10, stroke_fill=(0, 0, 0))
    tag = f"{place.get('country', '')}・{place['name']}"
    ft = F(40)
    d.rounded_rectangle([50, 40, 90 + d.textlength(tag, font=ft), 104], radius=12, fill=(220, 40, 40))
    d.text((70, 72), tag, font=ft, fill=(255, 255, 255), anchor="lm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=90)
    return out


def _ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def description(ep: dict, shots: list[compose.Shot], starts: list[float], credits: Credits, tts_credit: str,
                channel_note: str = "") -> str:
    lines = [ep.get("summary") or f"{ep['place'].get('country', '')}の{ep['place']['name']}を、地形・歴史・生態系から地理の目線で解説します。", ""]
    # 章（YouTube のチャプター: 0:00 から始まり、3つ以上・各10秒以上）
    chs, idx = [], 0
    for ch in ep["chapters"]:
        chs.append((starts[idx] if idx < len(starts) else 0, ch["title"]))
        idx += len(ch["segments"])
    chs[0] = (0, chs[0][1])
    lines += ["■ 目次"] + [f"{_ts(t)} {title}" for t, title in chs] + [""]
    if ep.get("glossary"):
        lines += ["■ この動画に出てくる地理用語"] + [f"・{g['term']}：{g['desc']}" for g in ep["glossary"]] + [""]
    if ep.get("sources"):
        lines += ["■ 参考資料"] + [f"・{s}" for s in ep["sources"]] + [""]
    lines += ["■ 映像・画像のクレジット"] + [f"・{c}" for c in credits.items.values()]
    if tts_credit:
        lines.append(f"・ナレーション: {tts_credit}")
    lines += ["", "※解説は公開資料をもとに作成しています。誤りに気づいたらコメントで教えてください。"]
    if channel_note:
        lines += ["", channel_note]
    tags = ep.get("tags", [])[:6]
    lines += ["", " ".join("#" + t for t in tags)]
    return "\n".join(lines)[:4990]


def build(ep: dict, out_dir: Path, w: int = 1920, h: int = 1080, fps: int = 24, tts: TTS | None = None,
          bgm: Path | None = None, folder: Path | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    credits = Credits()
    shots = plan_shots(ep, w, h, fps, credits, folder)
    meta = compose.render(shots, out_dir / "episode.mp4", w, h, fps, tts=tts, bgm=bgm)
    thumb = thumbnail(ep, out_dir / "thumbnail.jpg")
    desc = description(ep, shots, meta["starts"], credits, tts.credit if tts else "")
    (out_dir / "description.txt").write_text(desc, encoding="utf-8")
    (out_dir / "episode.json").write_text(json.dumps(ep, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**meta, "thumbnail": str(thumb), "description": desc, "title": ep["title"], "tags": ep.get("tags", []),
            "minutes": round(meta["duration"] / 60, 1)}


def teaser(ep: dict, out_dir: Path, tts: TTS | None = None, video_url: str = "", bgm: Path | None = None) -> dict:
    """本編の冒頭から、縦型ショート（約40〜60秒）を作る。概要欄から本編へ誘導する。"""
    first = ep["chapters"][0]
    segs = list(first["segments"][:3])
    nxt = next((s for ch in ep["chapters"][1:] for s in ch["segments"] if s["visual"]["type"] == "term"), None)
    if nxt:
        segs.append(nxt)
    segs.append({"text": "この続きは、本編の動画でくわしく解説しています。",
                 "visual": {"type": "photo", "query": ep["place"].get("name_en") or ep["place"]["name"]}})
    short = {**ep, "chapters": [{"title": "", "segments": segs}]}
    credits = Credits()
    shots = plan_shots(short, 1080, 1920, 30, credits)
    for sh in shots:
        sh.title = ""
    meta = compose.render(shots, out_dir / "teaser.mp4", 1080, 1920, 30, tts=tts, bgm=bgm)
    desc = (f"{ep.get('summary', '')}\n\n▶ 本編: {video_url}\n\n" if video_url else f"{ep.get('summary', '')}\n\n")
    desc += "映像・画像: " + " / ".join(credits.items.values())
    if tts and tts.credit:
        desc += f"\nナレーション: {tts.credit}"
    desc += "\n\n" + " ".join("#" + t for t in ep.get("tags", [])[:4]) + " #Shorts"
    title = (ep.get("thumbnail_text", "").replace("\n", "") or ep["place"]["name"]) + f"｜{ep['place']['name']}の地理 #Shorts"
    return {**meta, "title": title[:100], "description": desc[:4900]}


__all__ = ["build", "teaser", "thumbnail", "description", "plan_shots"]
