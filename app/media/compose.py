"""ショットを並べてナレーション付きの動画にする。

ショット = 背景（衛星ズーム / 映像 / 写真のケン・バーンズ / カード）× 長さ × 重ねる文字（字幕・章タイトル・用語カード・出典）。
各ショットの長さは、そのショットで読み上げる文の音声の長さで決まる（字幕は文ごとに切り替わる）。
フレームは Pillow で合成して ffmpeg に流す。映像素材は ffmpeg で1フレームずつ読み出す。
"""
from __future__ import annotations

import logging
import random
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from ..content.tts import TTS, split_sentences, wav_frames
from ..content.video import Fonts, wrap

log = logging.getLogger(__name__)
RATE = 24000


# ---------------------------------------------------------------- 背景ソース
class Source:
    def frame(self, t: float) -> Image.Image:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:
        pass


class Solid(Source):
    def __init__(self, img: Image.Image):
        self.img = img

    def frame(self, t: float) -> Image.Image:
        return self.img.copy()


class KenBurns(Source):
    """写真をゆっくりズーム・パンする。"""

    def __init__(self, img: Image.Image, w: int, h: int, duration: float, seed: int = 0):
        self.w, self.h, self.d = w, h, max(duration, 0.1)
        base = ImageOps.fit(img.convert("RGB"), (int(w * 1.18), int(h * 1.18)), Image.LANCZOS)
        self.base = base
        rnd = random.Random(seed)
        self.zoom_in = rnd.random() < 0.6
        self.dx, self.dy = rnd.uniform(-1, 1), rnd.uniform(-0.5, 0.5)

    def frame(self, t: float) -> Image.Image:
        k = t / self.d
        s = 1.0 + 0.15 * (k if self.zoom_in else 1 - k)     # 1.0〜1.15
        cw, ch = self.w * 1.18 / s, self.h * 1.18 / s
        bw, bh = self.base.size
        cx = bw / 2 + self.dx * (bw - cw) / 2 * (k - 0.5) * 2 * 0.9
        cy = bh / 2 + self.dy * (bh - ch) / 2 * (k - 0.5) * 2 * 0.9
        cx = min(max(cx, cw / 2), bw - cw / 2)
        cy = min(max(cy, ch / 2), bh - ch / 2)
        box = (max(0.0, cx - cw / 2), max(0.0, cy - ch / 2), min(bw, cx + cw / 2), min(bh, cy + ch / 2))
        return self.base.resize((self.w, self.h), Image.BILINEAR, box=box)


class VideoClip(Source):
    """映像素材を画面いっぱいに切り抜いて、時間順に1フレームずつ返す（短ければループ）。"""

    def __init__(self, path: str, w: int, h: int, fps: int, start: float = 1.0):
        self.w, self.h = w, h
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"
        self.p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-ss", str(start), "-i", path,
             "-an", "-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE)
        self.size = w * h * 3
        self.last = Image.new("RGB", (w, h))

    def frame(self, t: float) -> Image.Image:
        assert self.p.stdout
        buf = self.p.stdout.read(self.size)
        if len(buf) == self.size:
            self.last = Image.frombytes("RGB", (self.w, self.h), buf)
        return self.last.copy()

    def close(self) -> None:
        self.p.kill()
        self.p.wait()


# ---------------------------------------------------------------- ショット
@dataclass
class Shot:
    source: Callable[[], Source]           # 遅延生成（素材を開くのは描画の直前）
    sentences: list[str]
    title: str = ""                        # 章タイトル（ショットの最初に下部に出す）
    credit: str = ""                       # 左上の小さな出典表記
    overlay: Callable[[Image.Image, float, "Shot"], Image.Image] | None = None
    min_duration: float = 2.5
    # 描画時に埋まる
    timings: list[tuple[float, float]] = field(default_factory=list)
    duration: float = 0.0


def narrate(shots: list[Shot], tts: TTS | None, gap: float = 0.28, chars_per_sec: float = 7.5) -> bytes:
    """各ショットの文を読み上げて長さを決め、1本の PCM を返す。"""
    pcm = bytearray()
    for sh in shots:
        t = 0.25
        sh.timings = []
        chunk = bytearray(int(0.25 * RATE) * 2)
        for s in sh.sentences:
            audio = tts.synth(s) if tts else None
            if audio:
                frames, rate = wav_frames(audio)
                if rate != RATE:
                    a = np.frombuffer(frames, "<i2").astype(np.float32)
                    idx = np.linspace(0, len(a) - 1, int(len(a) * RATE / rate))
                    frames = np.interp(idx, np.arange(len(a)), a).astype("<i2").tobytes()
                dur = len(frames) / 2 / RATE
            else:
                frames, dur = b"", max(1.2, len(s) / chars_per_sec)
            chunk += frames + bytearray(max(0, int(dur * RATE) * 2 - len(frames))) + bytearray(int(gap * RATE) * 2)
            sh.timings.append((t, t + dur))
            t += dur + gap
        sh.duration = max(sh.min_duration, t + 0.2)
        n = int(round(sh.duration * RATE)) * 2
        pcm += chunk[:n] + bytearray(max(0, n - len(chunk)))
    return bytes(pcm)


# ---------------------------------------------------------------- 文字の描画
class Painter:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.k = w / 1920 if w > h else w / 1080   # 1080p 基準の倍率
        self.F = Fonts(self.k)

    def S(self, v: float) -> int:
        return int(v * self.k)

    def caption(self, img: Image.Image, text: str, vertical: bool = False) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        f = self.F(46 if not vertical else 54)
        maxw = self.w * (0.8 if not vertical else 0.84)
        lines = wrap(d, text, f, maxw)[:3]
        lh = f.size * 1.32
        y_bottom = self.h - (self.S(70) if not vertical else self.S(480))
        y0 = y_bottom - lh * len(lines)
        for i, ln in enumerate(lines):
            y = y0 + lh * (i + 0.5)
            d.text((self.w / 2, y), ln, font=f, fill=(255, 255, 255), anchor="mm",
                   stroke_width=max(2, self.S(5)), stroke_fill=(0, 0, 0))

    def chapter(self, img: Image.Image, title: str, a: float) -> None:
        if a <= 0:
            return
        d = ImageDraw.Draw(img, "RGBA")
        f = self.F(52)
        tw = d.textlength(title, font=f)
        x, y = self.S(70), self.S(90)
        al = int(210 * a)
        d.rectangle([x, y, x + self.S(12), y + self.S(80)], fill=(255, 196, 0, al))
        d.rounded_rectangle([x + self.S(22), y, x + self.S(60) + tw, y + self.S(80)], radius=self.S(10),
                            fill=(0, 0, 0, int(150 * a)))
        d.text((x + self.S(40), y + self.S(40)), title, font=f, fill=(255, 255, 255, int(255 * a)), anchor="lm")

    def credit(self, img: Image.Image, text: str) -> None:
        if not text:
            return
        d = ImageDraw.Draw(img, "RGBA")
        f = self.F(20)
        text = text if len(text) < 110 else text[:108] + "…"
        d.text((self.w - self.S(24), self.S(22)), text, font=f, fill=(255, 255, 255, 200), anchor="ra",
               stroke_width=max(1, self.S(2)), stroke_fill=(0, 0, 0, 160))

    def term_card(self, img: Image.Image, term: str, reading: str, desc: str, a: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.w, self.h
        cw, ch = (int(w * 0.62), int(h * 0.46)) if w > h else (int(w * 0.9), int(h * 0.3))
        x0, y0 = (w - cw) // 2, int(h * (0.18 if w > h else 0.25)) + int((1 - a) * self.S(40))
        d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=self.S(24), fill=(10, 16, 30, int(215 * a)),
                            outline=(255, 196, 0, int(255 * a)), width=max(2, self.S(4)))
        d.text((x0 + self.S(50), y0 + self.S(60)), "地理用語", font=self.F(30), fill=(255, 196, 0, int(255 * a)),
               anchor="lm")
        d.text((x0 + self.S(50), y0 + self.S(140)), term, font=self.F(84), fill=(255, 255, 255, int(255 * a)),
               anchor="lm")
        if reading:
            d.text((x0 + self.S(50), y0 + self.S(210)), reading, font=self.F(32), fill=(190, 200, 220, int(255 * a)),
                   anchor="lm")
        f = self.F(38)
        yy = y0 + self.S(270)
        for ln in wrap(d, desc, f, cw - self.S(100))[:4]:
            d.text((x0 + self.S(50), yy), ln, font=f, fill=(235, 238, 245, int(255 * a)), anchor="lm")
            yy += f.size * 1.4


# ---------------------------------------------------------------- 書き出し
def render(shots: list[Shot], out: Path, w: int = 1920, h: int = 1080, fps: int = 24, tts: TTS | None = None,
           bgm: Path | None = None, bgm_volume: float = 0.08, fade: float = 0.45) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg が必要です")
    out.parent.mkdir(parents=True, exist_ok=True)
    pcm = narrate(shots, tts)
    total = sum(s.duration for s in shots)
    painter = Painter(w, h)
    vertical = h > w
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voice.wav"
        with wave.open(str(wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(pcm)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
               "-r", str(fps), "-i", "-", "-i", str(wav)]
        if bgm and bgm.exists():
            cmd += ["-stream_loop", "-1", "-i", str(bgm), "-filter_complex",
                    f"[2:a]volume={bgm_volume},afade=t=out:st={max(0, total - 3):.2f}:d=3[b];"
                    "[1:a][b]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin
        prev_last: Image.Image | None = None
        starts, t0 = [], 0.0
        try:
            for sh in shots:
                starts.append(t0)
                src = sh.source()
                n = int(round(sh.duration * fps))
                last = None
                for k in range(n):
                    t = k / fps
                    img = src.frame(t)
                    if img.size != (w, h):
                        img = ImageOps.fit(img, (w, h))
                    if sh.overlay:
                        img = sh.overlay(img, t, sh) or img
                    if sh.title:
                        a = min(1.0, t / 0.5) * min(1.0, max(0.0, (4.5 - t) / 0.5))
                        painter.chapter(img, sh.title, a)
                    for (s0, s1), text in zip(sh.timings, sh.sentences):
                        if s0 - 0.1 <= t < s1 + 0.25:
                            painter.caption(img, text, vertical)
                            break
                    painter.credit(img, sh.credit)
                    if prev_last is not None and t < fade:
                        img = Image.blend(prev_last, img, t / fade)
                    proc.stdin.write(img.tobytes())
                    last = img
                src.close()
                prev_last = last
                t0 += sh.duration
        finally:
            proc.stdin.close()
            code = proc.wait()
        if code:
            raise RuntimeError(f"ffmpeg が失敗しました (exit {code})")
    return {"path": str(out), "duration": round(total, 2), "starts": starts}
