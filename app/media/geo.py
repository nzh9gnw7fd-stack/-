"""衛星画像で「宇宙から地球儀を回して、目的地へズームしていく」映像を描く（Google Earth 風）。

Google Earth の映像は自動では作れず、規約上も自動生成の動画には使えないため、
自由に使える衛星画像タイルを自前で描画している。
  - 広域: NASA Blue Marble（GIBS, パブリックドメイン）
  - 地表: Sentinel-2 cloudless 2016 by EOX（CC BY 4.0、要クレジット。2017年以降の版は非商用なので使わない）
自分で Google Earth Studio から書き出した映像を使いたい場合は、エピソードの素材フォルダに置けば優先して使う
（その場合は画面と概要欄に「Google Earth」の表記が必要）。
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import config
from .assets import UA

log = logging.getLogger(__name__)
TILE = 256
CACHE = Path(os.getenv("SVWB_TILE_CACHE", config.DATA_DIR / "tile_cache"))
SOURCES = {
    "bluemarble": ("https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/"
                   "GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg", 8),
    "s2": ("https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg", 15),
}
CREDITS = {
    "bluemarble": "衛星画像: NASA Blue Marble (NASA Earth Observatory / GIBS)",
    "s2": "衛星画像: Sentinel-2 cloudless 2016 by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016) / CC BY 4.0",
}


# ---------------------------------------------------------------- タイル
def _fetch(src: str, z: int, x: int, y: int, client: httpx.Client) -> Image.Image:
    url, _ = SOURCES[src]
    n = 2 ** z
    x %= n
    if not 0 <= y < n:
        return Image.new("RGB", (TILE, TILE), (8, 14, 32))
    p = CACHE / src / str(z) / f"{x}_{y}.jpg"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = client.get(url.format(z=z, x=x, y=y), timeout=30)
            r.raise_for_status()
            p.write_bytes(r.content)
        except httpx.HTTPError as e:
            log.debug("tile %s %s/%s/%s: %s", src, z, x, y, e)
            return Image.new("RGB", (TILE, TILE), (8, 14, 32))
    try:
        return Image.open(p).convert("RGB")
    except OSError:
        p.unlink(missing_ok=True)
        return Image.new("RGB", (TILE, TILE), (8, 14, 32))


def lonlat_to_px(lon: float, lat: float, z: float) -> tuple[float, float]:
    lat = max(-85.05, min(85.05, lat))
    n = TILE * 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def mosaic(src: str, z: int, cx: float, cy: float, w: int, h: int) -> Image.Image:
    """レベル z のピクセル座標 (cx, cy) を中心にした w×h の画像。"""
    x0, y0 = cx - w / 2, cy - h / 2
    tx0, ty0 = int(math.floor(x0 / TILE)), int(math.floor(y0 / TILE))
    tx1, ty1 = int(math.floor((x0 + w) / TILE)), int(math.floor((y0 + h) / TILE))
    img = Image.new("RGB", ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE))
    coords = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    with httpx.Client(headers=UA, follow_redirects=True) as c, ThreadPoolExecutor(8) as ex:
        tiles = list(ex.map(lambda t: _fetch(src, z, t[0], t[1], c), coords))
    for (tx, ty), t in zip(coords, tiles):
        img.paste(t, ((tx - tx0) * TILE, (ty - ty0) * TILE))
    ox, oy = int(x0 - tx0 * TILE), int(y0 - ty0 * TILE)
    return img.crop((ox, oy, ox + w, oy + h))


# ---------------------------------------------------------------- 地球儀
class Globe:
    """Blue Marble をメルカトルで貼った正射図法の地球儀。"""

    def __init__(self, level: int = 3):
        n = TILE * 2 ** level
        self.tex = np.asarray(mosaic("bluemarble", level, n / 2, n / 2, n, n), dtype=np.uint8)
        self.n = n

    def render(self, w: int, h: int, lat0: float, lon0: float, radius: float, stars: np.ndarray) -> Image.Image:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        x = (xx - w / 2) / radius
        y = -(yy - h / 2) / radius
        rho2 = x * x + y * y
        inside = rho2 <= 1
        z = np.sqrt(np.clip(1 - rho2, 0, 1))
        p0, l0 = math.radians(lat0), math.radians(lon0)
        lat = np.arcsin(np.clip(z * math.sin(p0) + y * math.cos(p0), -1, 1))
        lon = l0 + np.arctan2(x, z * math.cos(p0) - y * math.sin(p0))
        latc = np.clip(lat, math.radians(-85.0), math.radians(85.0))
        u = ((lon / (2 * math.pi) + 0.5) % 1.0) * (self.n - 1)
        v = (1 - np.log(np.tan(latc) + 1 / np.cos(latc)) / math.pi) / 2 * (self.n - 1)
        col = self.tex[v.astype(np.int32).clip(0, self.n - 1), u.astype(np.int32).clip(0, self.n - 1)].astype(np.float32)
        shade = (0.55 + 0.45 * z)[..., None]  # 縁を暗く（立体感）
        out = stars.astype(np.float32).copy()
        out[inside] = (col * shade)[inside]
        # 大気のにじみ
        r = np.sqrt(rho2)
        glow = np.clip(1 - (r - 1) / 0.08, 0, 1) * (r > 1)
        out += glow[..., None] * np.array([70, 130, 255], np.float32) * 0.6
        edge = np.clip((r - 0.9) / 0.1, 0, 1) * inside
        out = out * (1 - edge[..., None] * 0.25) + edge[..., None] * np.array([90, 150, 255], np.float32) * 0.25
        return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def starfield(w: int, h: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (3, 5, 12)
    n = w * h // 900
    ys, xs = rng.integers(0, h, n), rng.integers(0, w, n)
    b = rng.integers(60, 255, n)
    img[ys, xs] = np.stack([b, b, np.minimum(255, b + 20)], 1)
    return img


# ---------------------------------------------------------------- ズーム映像
def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


@dataclass
class EarthZoom:
    """frame(t) で t 秒目の画像を返す。目的地へ「地球儀→地表」とズームする。"""
    lat: float
    lon: float
    zoom: float                     # 最終ズーム（9=地方、11=都市、13=街区）
    duration: float
    w: int = 1920
    h: int = 1080
    label: str = ""
    start_lon: float | None = None  # 前の場所から回す
    start_lat: float | None = None
    fonts: object | None = None
    _globe: Globe | None = field(default=None, repr=False)
    _mos: dict = field(default_factory=dict, repr=False)
    _stars: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self):
        self.t_globe = min(4.0, self.duration * 0.3)
        self.t_zoom = min(7.0, self.duration * 0.45)
        self.z_switch = 4.2  # ここで地球儀から平面地図に切り替える
        self.zoom = min(self.zoom, SOURCES["s2"][1] - 0.2)

    @property
    def credits(self) -> list[str]:
        return [CREDITS["bluemarble"]] + ([CREDITS["s2"]] if self.zoom > 5.5 else [])

    def _flat_zoom_for_radius(self, r: float) -> float:
        return math.log2(max(1e-6, 2 * math.pi * r * math.cos(math.radians(self.lat)) / TILE))

    def _radius_for_flat_zoom(self, z: float) -> float:
        return TILE * 2 ** z / (2 * math.pi * math.cos(math.radians(self.lat)))

    def zoom_at(self, t: float) -> float:
        if t < self.t_globe:
            return -1
        k = ease((t - self.t_globe) / self.t_zoom)
        z = self.z_switch + (self.zoom - self.z_switch) * k
        if t > self.t_globe + self.t_zoom:  # その後もゆっくり寄り続ける
            z = self.zoom + 0.25 * (t - self.t_globe - self.t_zoom) / max(1, self.duration - self.t_globe - self.t_zoom)
        return z

    def _flat(self, z: float) -> Image.Image:
        level = int(math.ceil(z))
        src = "bluemarble" if level <= 6 else "s2"
        key = (src, level)
        if key not in self._mos:
            # 古いレベルを捨ててメモリを抑える
            for k in [k for k in self._mos if abs(k[1] - level) > 1]:
                del self._mos[k]
            cx, cy = lonlat_to_px(self.lon, self.lat, level)
            self._mos[key] = mosaic(src, level, cx, cy, self.w * 2 + 8, self.h * 2 + 8)
        m = self._mos[key]
        s = 2 ** (z - level)            # 0.5〜1
        cw, ch = self.w / s, self.h / s
        mx, my = m.width / 2, m.height / 2
        img = m.crop((int(mx - cw / 2), int(my - ch / 2), int(mx + cw / 2), int(my + ch / 2))).resize(
            (self.w, self.h), Image.BILINEAR)
        if 6.0 < z < 6.8 and src == "s2":  # Blue Marble → Sentinel-2 をなめらかにつなぐ
            prev = self._flat_src(z, "bluemarble", 6)
            img = Image.blend(prev, img, ease((z - 6.0) / 0.8))
        return img

    def _flat_src(self, z: float, src: str, level: int) -> Image.Image:
        key = (src, level)
        if key not in self._mos:
            cx, cy = lonlat_to_px(self.lon, self.lat, level)
            self._mos[key] = mosaic(src, level, cx, cy, self.w * 2 + 8, self.h * 2 + 8)
        m = self._mos[key]
        s = 2 ** (z - level)
        cw, ch = self.w / s, self.h / s
        mx, my = m.width / 2, m.height / 2
        box = (int(mx - cw / 2), int(my - ch / 2), int(mx + cw / 2), int(my + ch / 2))
        return m.crop(box).resize((self.w, self.h), Image.BILINEAR)

    def frame(self, t: float) -> Image.Image:
        if self._stars is None:
            self._stars = starfield(self.w, self.h)
        r_switch = self._radius_for_flat_zoom(self.z_switch)
        if t < self.t_globe + 0.6:
            if self._globe is None:
                self._globe = Globe(3)
            k = ease(t / self.t_globe) if self.t_globe else 1
            slon = self.start_lon if self.start_lon is not None else self.lon - 70
            slat = self.start_lat if self.start_lat is not None else 10.0
            dlon = ((self.lon - slon + 180) % 360) - 180
            lat0 = slat + (self.lat - slat) * k
            lon0 = slon + dlon * k
            r0 = self.h * 0.36
            radius = r0 * (r_switch / r0) ** ease((t - self.t_globe * 0.55) / (self.t_globe * 0.45 + 0.6))
            g = self._globe.render(self.w, self.h, lat0, lon0, radius, self._stars)
            if t < self.t_globe:
                return g
            # 地球儀 → 平面地図のクロスフェード
            return Image.blend(g, self._flat(self.z_switch), ease((t - self.t_globe) / 0.6))
        return self._flat(self.zoom_at(t))

    def hud(self, t: float) -> dict:
        """画面に重ねる情報（緯度経度・高度・ピン）。"""
        z = self.zoom_at(t)
        if z < 0:
            alt_km = 20000.0
        else:
            m_per_px = 156543.03 * math.cos(math.radians(self.lat)) / 2 ** z
            alt_km = m_per_px * self.w * 0.87 / 1000
        return {"lat": self.lat, "lon": self.lon, "alt_km": alt_km,
                "pin": t > self.t_globe + self.t_zoom * 0.7, "label": self.label}


def draw_hud(img: Image.Image, hud: dict, font_fn, scale: float = 1.0) -> Image.Image:
    """Google Earth 風の表示（右下の座標・高度、中央のピンと地名）。"""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    S = lambda v: int(v * scale * w / 1920)  # noqa: E731
    lat, lon = hud["lat"], hud["lon"]
    txt = f"{abs(lat):.3f}°{'N' if lat >= 0 else 'S'}  {abs(lon):.3f}°{'E' if lon >= 0 else 'W'}   高度 {hud['alt_km']:,.0f} km"
    f = font_fn(S(26))
    tw = d.textlength(txt, font=f)
    d.rounded_rectangle([w - tw - S(60), h - S(70), w - S(24), h - S(24)], radius=S(10), fill=(0, 0, 0, 140))
    d.text((w - S(42), h - S(47)), txt, font=f, fill=(235, 240, 255), anchor="rm")
    if hud.get("pin"):
        cx, cy = w // 2, h // 2
        d.ellipse([cx - S(14), cy - S(14), cx + S(14), cy + S(14)], outline=(255, 70, 70), width=max(2, S(5)))
        d.ellipse([cx - S(5), cy - S(5), cx + S(5), cy + S(5)], fill=(255, 70, 70))
        if hud.get("label"):
            fl = font_fn(S(46))
            lw = d.textlength(hud["label"], font=fl)
            d.rounded_rectangle([cx + S(30), cy - S(80), cx + S(70) + lw, cy - S(18)], radius=S(12), fill=(0, 0, 0, 170))
            d.text((cx + S(50), cy - S(49)), hud["label"], font=fl, fill=(255, 255, 255), anchor="lm")
            d.line([cx + S(10), cy - S(10), cx + S(30), cy - S(30)], fill=(255, 255, 255), width=max(1, S(3)))
    return img


def still(lat: float, lon: float, zoom: float, w: int, h: int) -> Image.Image:
    """サムネイルや背景に使う1枚の衛星画像。"""
    z = EarthZoom(lat, lon, zoom, 10, w, h)
    return z._flat(min(zoom, SOURCES["s2"][1] - 0.2))


def blurred(img: Image.Image, radius: int = 18, dim: float = 0.55) -> Image.Image:
    return Image.eval(img.filter(ImageFilter.GaussianBlur(radius)), lambda v: int(v * dim))


def cache_key(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]
