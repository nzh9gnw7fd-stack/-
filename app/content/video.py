"""縦型ショート動画（1080x1920, 30fps）を描画して mp4 にする。

絵はすべて自前で描く（ゲームのカード画像や公式素材は使わない＝権利面で安全）。
Pillow でフレームを描いて ffmpeg の標準入力に流す。アニメーションは各シーンの最初の約1秒だけで、
その後は同じフレームを使い回すので速い（40秒の動画で数十秒）。

ショートの画面は上部に検索アイコン、下部と右側にタイトル・ボタンが重なるので、
大事な文字は中央の安全領域（左右 70px、上 200px、下 430px を避ける）に置く。
"""
from __future__ import annotations

import io
import logging
import os
import random
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .tts import TTS, wav_frames
from .writer import DISCLAIMER, Scene

log = logging.getLogger(__name__)

W, H, FPS = 1080, 1920, 30
RATE = 24000
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]


def font_path() -> str:
    for p in [os.getenv("SVWB_FONT", ""), *FONT_CANDIDATES]:
        if p and Path(p).exists():
            return p
    raise RuntimeError("日本語フォントが見つかりません。fonts-noto-cjk を入れるか SVWB_FONT を設定してください")


class Fonts:
    def __init__(self, scale: float = 1.0):
        self.path = font_path()
        self.scale = scale
        self._cache: dict[int, ImageFont.FreeTypeFont] = {}

    def __call__(self, size: float) -> ImageFont.FreeTypeFont:
        px = max(8, int(size * self.scale))
        if px not in self._cache:
            self._cache[px] = ImageFont.truetype(self.path, px)
        return self._cache[px]


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a, b, t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def wrap(draw: ImageDraw.ImageDraw, text: str, font, width: float) -> list[str]:
    """日本語向けの折り返し（文字単位。行頭禁則だけ簡易対応）。"""
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if draw.textlength(cur + ch, font=font) > width and cur:
                if ch in "、。！？」）ー…%":
                    cur += ch
                    continue
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def fit(draw, text: str, fonts: Fonts, width: float, start: int, minimum: int, max_lines: int):
    # まず1行に収まる大きさを探す（単語の途中で折り返すと読みにくい）
    size = start
    while size >= max(minimum, int(start * 0.6)):
        f = fonts(size)
        if draw.textlength(text, font=f) <= width * fonts.scale and "\n" not in text:
            return f, [text]
        size -= 4
    size = start
    while size > minimum:
        f = fonts(size)
        lines = wrap(draw, text, f, width * fonts.scale)
        if len(lines) <= max_lines:
            return f, lines
        size -= 4
    f = fonts(minimum)
    return f, wrap(draw, text, f, width * fonts.scale)[:max_lines]


@dataclass
class Timed:
    scene: Scene
    start: float
    dur: float
    audio: bytes | None = None


class Renderer:
    def __init__(self, scale: float = 1.0, brand: str = "", footer: str = DISCLAIMER):
        self.s = scale
        self.footer = footer
        self.w, self.h = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
        self.fonts = Fonts(scale)
        self.brand = brand
        self._bg: dict[str, Image.Image] = {}

    def S(self, v: float) -> int:
        return int(v * self.s)

    def background(self, accent: str) -> Image.Image:
        if accent not in self._bg:
            top, bottom = (12, 14, 24), mix((18, 20, 32), hex_rgb(accent), 0.35)
            img = Image.new("RGB", (self.w, self.h))
            d = ImageDraw.Draw(img)
            for y in range(self.h):
                d.line([(0, y), (self.w, y)], fill=mix(top, bottom, (y / self.h) ** 1.4))
            # 斜めのストライプで単調さを消す
            rnd = random.Random(accent)
            for _ in range(6):
                x = rnd.randint(-self.w, self.w)
                d.polygon([(x, 0), (x + self.S(120), 0), (x + self.S(120) + self.h // 2, self.h),
                           (x + self.h // 2, self.h)], fill=mix(top, hex_rgb(accent), 0.08))
            self._bg[accent] = img
        return self._bg[accent]

    # ------------------------------------------------------------ 1フレーム
    def frame(self, sc: Scene, t: float, progress: float) -> Image.Image:
        img = self.background(sc.color).copy()
        d = ImageDraw.Draw(img)
        S, F = self.S, self.fonts
        accent = hex_rgb(sc.color)
        cx = self.w // 2
        a = ease(t / 0.45)  # 出現アニメーション

        # 上部: ブランドと進行バー
        d.rectangle([0, 0, int(self.w * progress), S(10)], fill=accent)
        if self.brand:
            d.text((cx, S(200)), self.brand, font=F(30), fill=(170, 172, 185), anchor="mm")

        # 見出しピル
        if sc.heading:
            f = F(46)
            tw = d.textlength(sc.heading, font=f)
            y = S(300) - int((1 - a) * S(40))
            d.rounded_rectangle([cx - tw / 2 - S(36), y - S(44), cx + tw / 2 + S(36), y + S(44)], radius=S(44),
                                fill=accent if sc.kind != "title" else (255, 255, 255))
            d.text((cx, y), sc.heading, font=f, anchor="mm",
                   fill=(15, 15, 20) if sum(accent) > 450 or sc.kind == "title" else (255, 255, 255))

        if sc.kind in ("title", "focus", "cta"):
            self._big(d, sc, a)
        if sc.kind in ("bars", "matchup") and sc.bars:
            self._bars(d, sc, t)
        if sc.kind == "matchup":
            f = F(64)
            d.text((cx, S(560)), sc.big, font=f, fill=(255, 255, 255), anchor="mm")
            d.text((cx, S(650)), "▼ に強い ▼", font=F(40), fill=accent, anchor="mm")
            d.text((cx, S(740)), sc.sub, font=f, fill=(220, 220, 228), anchor="mm")

        if sc.badge:
            f = F(36)
            tw = d.textlength(sc.badge, font=f)
            x, y = self.w - S(90) - tw, S(420)
            d.rounded_rectangle([x - S(20), y - S(30), x + tw + S(20), y + S(30)], radius=S(12), outline=accent,
                                width=max(1, S(4)))
            d.text((x + tw / 2, y), sc.badge, font=f, fill=accent, anchor="mm")

        self._caption(d, sc.caption, a)
        if self.footer:
            d.text((cx, S(1610)), self.footer, font=F(26), fill=(150, 152, 165), anchor="mm")
        return img

    def _big(self, d, sc: Scene, a: float):
        S, F = self.S, self.fonts
        cx = self.w // 2
        f, lines = fit(d, sc.big, F, 900, 150 if sc.kind == "title" else 120, 64, 3)
        lh = f.size * 1.18
        y0 = S(820) - lh * (len(lines) - 1) / 2 + (1 - a) * S(60)
        for i, ln in enumerate(lines):
            y = y0 + i * lh
            d.text((cx + S(6), y + S(6)), ln, font=f, fill=(0, 0, 0), anchor="mm")
            d.text((cx, y), ln, font=f, fill=(255, 255, 255) if sc.kind != "focus" else mix(
                (255, 255, 255), hex_rgb(sc.color), 0.15), anchor="mm")
        if sc.sub:
            fs = F(54)
            yy = y0 + len(lines) * lh + S(40)
            for ln in wrap(d, sc.sub, fs, S(920)):
                d.text((cx, yy), ln, font=fs, fill=(225, 226, 235), anchor="mm")
                yy += fs.size * 1.35
        if sc.kind == "focus":
            d.rounded_rectangle([cx - S(160), S(560), cx + S(160), S(572)], radius=S(6), fill=hex_rgb(sc.color))

    def _bars(self, d, sc: Scene, t: float):
        S, F = self.S, self.fonts
        n = len(sc.bars)
        top = S(470) if sc.kind == "bars" else S(880)
        gap = min(S(170), (S(1380) - top) // max(n, 1))
        maxw = S(900)
        for i, (label, val, text, col) in enumerate(sc.bars):
            g = ease((t - i * 0.12) / 0.7)
            y = top + i * gap
            d.text((S(90), y), label, font=F(46), fill=(240, 240, 245), anchor="lm")
            by = y + S(56)
            d.rounded_rectangle([S(90), by - S(22), S(90) + maxw, by + S(22)], radius=S(22), fill=(40, 42, 56))
            wv = max(S(44), int(maxw * max(0.0, min(1.0, float(val))) * g))
            d.rounded_rectangle([S(90), by - S(22), S(90) + wv, by + S(22)], radius=S(22), fill=hex_rgb(col))
            d.text((S(90) + maxw, y), text, font=F(46), fill=(255, 255, 255), anchor="rm")

    def _caption(self, d, text: str, a: float):
        S, F = self.S, self.fonts
        f = F(50)
        lines = wrap(d, text, f, S(880))[:3]
        lh = f.size * 1.3
        h = lh * len(lines) + S(40)
        y1 = S(1440)
        y0 = y1 - h
        d.rounded_rectangle([S(70), y0, self.w - S(70), y1], radius=S(28), fill=(0, 0, 0))
        for i, ln in enumerate(lines):
            d.text((self.w // 2, y0 + S(20) + lh * (i + 0.5)), ln, font=f, fill=(255, 236, 120), anchor="mm")


# ---------------------------------------------------------------- 書き出し
def plan(scenes: list[Scene], tts: TTS | None) -> tuple[list[Timed], bytes]:
    """各シーンの長さを決め、ナレーションを1本の PCM にまとめる。"""
    timed: list[Timed] = []
    pcm = bytearray()
    t = 0.0
    for sc in scenes:
        audio = tts.synth(sc.caption) if tts else None
        lead = 0.15
        if audio:
            frames, rate = wav_frames(audio)
            if rate != RATE:
                frames = _resample(frames, rate, RATE)
            speech = len(frames) / 2 / RATE
            dur = max(1.8, speech + lead + 0.3)
        else:
            frames = b""
            dur = max(2.2, min(5.5, len(sc.caption) / 8 + 0.8))
        n = int(round(dur * RATE))
        chunk = bytearray(int(lead * RATE) * 2) + frames
        chunk = chunk[: n * 2] + bytearray(max(0, n * 2 - len(chunk)))
        pcm += chunk
        timed.append(Timed(sc, t, n / RATE, audio))
        t += n / RATE
    return timed, bytes(pcm)


def _resample(pcm: bytes, src: int, dst: int) -> bytes:
    import array

    a = array.array("h", pcm)
    n = int(len(a) * dst / src)
    out = array.array("h", (a[min(len(a) - 1, int(i * src / dst))] for i in range(n)))
    return out.tobytes()


def pick_bgm() -> Path | None:
    from .. import config

    d = config.ROOT / "assets" / "bgm"
    files = sorted(p for p in d.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")) if d.exists() else []
    if not files:
        return None
    from datetime import date

    return files[date.today().toordinal() % len(files)]


def render(scenes: list[Scene], out: Path, tts: TTS | None = None, scale: float = 1.0, brand: str = "",
           bgm: Path | None = None, bgm_volume: float = 0.12, footer: str = DISCLAIMER) -> dict:
    """mp4 を書き出し、{path, duration, thumbnail} を返す。"""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg が必要です（apt install ffmpeg）")
    out.parent.mkdir(parents=True, exist_ok=True)
    timed, pcm = plan(scenes, tts)
    total = sum(x.dur for x in timed)
    r = Renderer(scale, brand=brand, footer=footer)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voice.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{r.w}x{r.h}", "-r", str(FPS), "-i", "-", "-i", str(wav)]
        if bgm and bgm.exists():
            cmd += ["-stream_loop", "-1", "-i", str(bgm), "-filter_complex",
                    f"[2:a]volume={bgm_volume},afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5[b];"
                    "[1:a][b]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin
        thumb = None
        try:
            for x in timed:
                nframes = int(round(x.dur * FPS))
                cached = None
                for k in range(nframes):
                    t = k / FPS
                    if cached is None or t < 1.2:
                        img = r.frame(x.scene, t, (x.start + t) / total)
                        buf = img.tobytes()
                        if t >= 1.2:
                            cached = buf
                        if thumb is None and x.scene.kind == "title" and t >= 1.0:
                            thumb = img
                    proc.stdin.write(cached or buf)
        finally:
            proc.stdin.close()
            code = proc.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg が失敗しました (exit {code})")
    meta = {"path": str(out), "duration": round(total, 2), "voiced": any(x.audio for x in timed)}
    if thumb is not None:
        tp = out.with_suffix(".png")
        thumb.save(tp, optimize=True)
        meta["thumbnail"] = str(tp)
    return meta


def still(scene: Scene, out: Path, brand: str = "", scale: float = 1.0, footer: str = DISCLAIMER) -> Path:
    """SNS 用の静止画（シーンの完成形）。"""
    img = Renderer(scale, brand=brand, footer=footer).frame(scene, 5.0, 1.0)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    out.write_bytes(buf.getvalue())
    return out


__all__ = ["render", "still", "Renderer", "plan"]
