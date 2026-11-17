"""動画素材・合成・地理チャンネルのテスト（ネットワークには接続しない）。"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from app.content.tts import split_sentences
from app.geo import build, script
from app.media import assets, compose, geo

TMP = Path(tempfile.mkdtemp())
ROOT = Path(__file__).resolve().parent.parent


def test_split_sentences():
    s = split_sentences("氷河が谷を削りました。やがて海水が入り込み、山の奥まで海が続く、細長くて深くて静かで美しい入り江ができあがったのです。")
    assert s[0] == "氷河が谷を削りました。"
    assert all(len(x) <= 48 for x in s) and "".join(s).endswith("のです。")


def test_mercator_pixels():
    x, y = geo.lonlat_to_px(0, 0, 0)
    assert (round(x), round(y)) == (128, 128)
    x, _ = geo.lonlat_to_px(180, 0, 1)
    assert round(x) == 512


def test_commons_license_filter(monkeypatch):
    def fake(c, url, params, tries=5):
        class R:
            def json(self):
                info = lambda lic, w=3000, url="https://upload.wikimedia.org/x/thumb/a.jpg/1920px-a.jpg": {  # noqa: E731
                    "imageinfo": [{"mime": "image/jpeg", "width": w, "height": 2000, "thumburl": url,
                                   "url": url, "descriptionurl": "https://commons.wikimedia.org/wiki/File:a.jpg",
                                   "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": "<a>Taro</a>"}}}]}
                return {"query": {"pages": {
                    "1": {"index": 1, "title": "File:ok.jpg", **info("CC BY-SA 4.0")},
                    "2": {"index": 2, "title": "File:nc.jpg", **info("CC BY-NC 2.0")},
                    "3": {"index": 3, "title": "File:small.jpg", **info("CC0", w=300)},
                    "4": {"index": 4, "title": "File:fairuse.jpg", **info("Fair use")},
                }}}
        return R()
    monkeypatch.setattr(assets, "_polite_get", fake)
    got = assets.commons("fjord", "image", 5)
    assert [a.title for a in got] == ["ok.jpg"]
    assert got[0].credit == "Taro" and got[0].license == "CC BY-SA 4.0"


def test_finalize_clamps_far_coordinates():
    data = {"title": "t", "thumbnail_text": "a\nb", "summary": "s", "tags": ["x"], "glossary": [], "review": "",
            "chapters": [{"title": "c", "segments": [
                {"text": "a。", "visual": {"type": "photo", "query": None}},
                {"text": "b。", "visual": {"type": "earth", "lat": 35.0, "lon": 139.0, "zoom": 30}},
                {"text": "c。", "visual": {"type": "term", "term": None}}]}]}
    ep = script.finalize(data, {"name": "死海", "wiki_en": "Dead Sea", "zoom": 9.5}, {"lat": 31.5, "lon": 35.5, "sources": []})
    v = [s["visual"] for s in ep["chapters"][0]["segments"]]
    assert v[0]["type"] == "earth" and v[0]["lat"] == 31.5          # 最初は必ず目的地への地球ズーム
    assert (v[1]["lat"], v[1]["lon"], v[1]["zoom"]) == (31.5, 35.5, 13.5)  # 遠すぎる座標・ズームは補正
    assert v[2]["type"] == "photo"                                   # 中身のない用語カードは写真に


def test_geo_schema_is_strict():
    s = script.schema()
    assert s["additionalProperties"] is False
    seg = s["properties"]["chapters"]["items"]["properties"]["segments"]["items"]
    assert set(seg["properties"]["visual"]["required"]) == set(seg["properties"]["visual"]["properties"])


def test_sample_episode_is_valid():
    ep = json.loads((ROOT / "episodes" / "sample_geiranger.json").read_text(encoding="utf-8"))
    assert ep["chapters"][0]["segments"][0]["visual"]["type"] == "earth"
    kinds = {s["visual"]["type"] for c in ep["chapters"] for s in c["segments"]}
    assert {"earth", "photo", "term", "map"} <= kinds


def test_description_has_chapters_and_credits():
    ep = json.loads((ROOT / "episodes" / "sample_geiranger.json").read_text(encoding="utf-8"))
    shots = [compose.Shot(source=lambda: None, sentences=["a"]) for c in ep["chapters"] for _ in c["segments"]]
    starts = [i * 15.0 for i in range(len(shots))]
    cr = build.Credits()
    cr.add("s2", geo.CREDITS["s2"])
    d = build.description(ep, shots, starts, cr, "VOICEVOX:青山龍星")
    assert "0:00 北欧の深い入り江へ" in d and "CC BY 4.0" in d and "VOICEVOX:青山龍星" in d
    assert d.count("\n0:") + d.count("\n1:") + d.count("\n2:") >= 3


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg がない")
def test_compose_render_small():
    from app.content.video import font_path

    try:
        font_path()
    except RuntimeError:
        pytest.skip("日本語フォントがない")
    img = Image.new("RGB", (800, 600), (30, 90, 160))
    painter = compose.Painter(320, 180)
    shots = [
        compose.Shot(source=lambda: compose.KenBurns(img, 320, 180, 3), sentences=["フィヨルドは氷河の谷です。"], title="第1章"),
        compose.Shot(source=lambda: compose.Solid(img.resize((320, 180))), sentences=["用語。"],
                     overlay=lambda im, t, sh: (painter.term_card(im, "U字谷", "", "氷河の谷", 1.0), im)[1]),
    ]
    m = compose.render(shots, TMP / "c.mp4", 320, 180, 12, tts=None)
    assert Path(m["path"]).stat().st_size > 1000 and len(m["starts"]) == 2 and m["duration"] > 4
