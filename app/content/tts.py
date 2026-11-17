"""読み上げ音声（任意）。VOICEVOX ENGINE の HTTP API を使う。

GitHub Actions ではサービスコンテナとして起動する（.github/workflows/content.yml）。
ローカルなら `docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest`。
VOICEVOX の音声を使った動画は、概要欄に「VOICEVOX:キャラクター名」のクレジットが必要（自動で入れる）。
"""
from __future__ import annotations

import io
import logging
import os
import wave

import httpx

log = logging.getLogger(__name__)

# 話者 ID → クレジット表記（よく使うもの）
SPEAKERS = {2: "四国めたん", 3: "ずんだもん", 8: "春日部つむぎ", 13: "青山龍星", 14: "冥鳴ひまり", 47: "ナースロボ＿タイプＴ"}


class TTS:
    def __init__(self, url: str | None = None, speaker: int | None = None, speed: float | None = None):
        self.url = (url or os.getenv("SVWB_VOICEVOX_URL", "")).rstrip("/")
        self.speaker = int(speaker or os.getenv("SVWB_VOICEVOX_SPEAKER", "3"))
        self.speed = float(speed or os.getenv("SVWB_VOICEVOX_SPEED", "1.2"))
        self._ok: bool | None = None

    @property
    def credit(self) -> str:
        return f"VOICEVOX:{SPEAKERS.get(self.speaker, f'話者{self.speaker}')}" if self.available() else ""

    def available(self) -> bool:
        if self._ok is None:
            self._ok = False
            if self.url:
                try:
                    self._ok = httpx.get(f"{self.url}/version", timeout=5).status_code == 200
                except httpx.HTTPError as e:
                    log.warning("VOICEVOX に接続できません（音声なしで作ります）: %s", e)
        return self._ok

    def synth(self, text: str) -> bytes | None:
        """16bit モノラル WAV のバイト列。失敗したら None。"""
        if not self.available() or not text.strip():
            return None
        try:
            q = httpx.post(f"{self.url}/audio_query", params={"text": text, "speaker": self.speaker}, timeout=60)
            q.raise_for_status()
            query = q.json()
            query.update(speedScale=self.speed, prePhonemeLength=0.05, postPhonemeLength=0.1,
                         outputSamplingRate=24000, outputStereo=False)
            r = httpx.post(f"{self.url}/synthesis", params={"speaker": self.speaker}, json=query, timeout=120)
            r.raise_for_status()
            return r.content
        except httpx.HTTPError as e:
            log.warning("読み上げに失敗: %s", e)
            return None


def wav_frames(blob: bytes) -> tuple[bytes, int]:
    """WAV から (PCM 16bit mono, サンプリングレート) を取り出す。"""
    with wave.open(io.BytesIO(blob)) as w:
        pcm = w.readframes(w.getnframes())
        if w.getnchannels() == 2:  # 念のためモノラル化（左チャンネル）
            import array

            a = array.array("h", pcm)
            pcm = a[0::2].tobytes()
        return pcm, w.getframerate()
