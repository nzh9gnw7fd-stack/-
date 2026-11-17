"""収益化コンテンツ（動画・記事・SNS・トレンド分析）のテスト。外部には一切接続しない。"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp())
os.environ["SVWB_DB_PATH"] = str(TMP / "content.db")

from app import pipeline  # noqa: E402
from app.archetypes import catalog  # noqa: E402
from app.content import blog, digest, social, topic_writer, trends, writer  # noqa: E402
from app.db import session  # noqa: E402
from app.sources import demo  # noqa: E402


@pytest.fixture(scope="module")
def dg():
    with session() as c:
        pipeline.store_posts(c, demo.generate(catalog(), 10, 150))
        c.commit()
        pipeline.extract_pending(c, use_llm=False)
        return digest.build(c)


def test_digest_publishable(dg):
    assert dg.publishable and dg.samples >= 30
    assert len(dg.top(5)) == 5


def test_digest_quality_gate_blocks_thin_data(dg):
    with session() as c:
        thin = digest.build(c, min_samples=10**9)
    assert not thin.publishable and thin.reasons
    assert thin.days == 30  # 最長の期間まで広げてから諦める


@pytest.mark.parametrize("kind", ["ranking", "trend", "winrate", "matchup", "rank"])
def test_scripts(dg, kind):
    sc = writer.script(dg, kind, tts_credit="VOICEVOX:ずんだもん")
    assert sc.scenes[0].kind == "title" and sc.scenes[-1].kind == "cta"
    assert len(sc.title) <= 100 and "#Shorts" in sc.title
    assert "VOICEVOX:ずんだもん" in sc.description
    assert all(s.caption for s in sc.scenes)


def test_sns_lengths(dg):
    t = writer.sns_posts(dg, "https://youtube.com/shorts/abc")
    assert len(t["bluesky"]) <= 300
    assert len(t["mastodon"]) <= 500
    assert writer.x_weight(t["x"]) <= 280


def test_article_and_weekly(dg):
    sc = writer.script(dg, "ranking")
    art = writer.article(dg, sc)
    assert art["slug"].startswith(dg.date) and art["blocks"]
    rep = writer.weekly_report(dg)
    assert "有料部分" in rep and "| デッキ |" in rep


def test_blog_build(dg, monkeypatch):
    monkeypatch.setattr(blog, "ARTICLES_DIR", TMP / "articles")
    blog.save(writer.article(dg, writer.script(dg, "ranking")))
    site = TMP / "site"
    assert blog.build(site) == 1
    assert (site / "articles" / "index.html").exists() and (site / "feed.xml").exists()
    page = next((site / "articles").glob("2*.html")).read_text(encoding="utf-8")
    assert "<table>" in page


def test_bsky_facets_use_byte_offsets():
    text = "環境速報 https://example.com/x #シャドバ"
    f = social.bsky_facets(text)
    link = next(x for x in f if x["features"][0]["$type"].endswith("#link"))
    b = text.encode()
    assert b[link["index"]["byteStart"]:link["index"]["byteEnd"]].decode() == "https://example.com/x"
    tag = next(x for x in f if x["features"][0]["$type"].endswith("#tag"))
    assert b[tag["index"]["byteStart"]:tag["index"]["byteEnd"]].decode() == "#シャドバ"


def test_oauth1_signature_matches_x_docs():
    # developer.x.com の「Creating a signature」の例
    h = social.oauth1_header(
        "POST", "https://api.twitter.com/1.1/statuses/update.json",
        "xvz1evFS4wEEPTGEFPHBog", "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
        "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
        params={"include_entities": "true", "status": "Hello Ladies + Gentlemen, a signed OAuth request!"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", ts="1318622958")
    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in h


def test_trend_scoring_prefers_pain_and_outliers():
    E = trends.Evidence
    by = {("money", "貯金 できない"): [E("youtube", "貯金できない人の特徴3選", views=900_000, subs=20_000, hours=50)],
          ("health", "寝つき 悪い"): [E("youtube", "夜のルーティン", views=50_000, subs=500_000, hours=100)]}
    ideas = trends.score_ideas(by, [], [], {}, {})
    assert ideas[0].niche == "money" and "できない" in ideas[0].pains
    # 最近使ったネタは点数が下がる
    again = trends.score_ideas(by, [], [], {"topics": [{"topic": "貯金 できない"}]}, {})
    assert next(i for i in again if i.topic == "貯金 できない").score < ideas[0].score


def test_performance_weights():
    hist = {"videos": [{"niche": "money", "views": v} for v in (10_000, 20_000)]
            + [{"niche": "health", "views": v} for v in (500, 800)]}
    w = trends.performance_weights(hist)
    assert w["money"] > 1 > w["health"]


def test_topic_script_shape():
    idea = trends.Idea("money", "貯金 できない", 1.0)
    data = {"title": "貯金できない人の習慣", "hook": "なぜかお金が残らない人へ。", "hook_screen": "貯金できない人",
            "points": [{"head": "先取り", "say": "給料日に別口座へ。"}] * 3, "outro": "保存してね。",
            "description": "コツ。", "hashtags": ["節約"], "risk": "low", "needs_fact_check": False, "risk_note": ""}
    sc = topic_writer.to_script(idea, data)
    assert [s.kind for s in sc.scenes] == ["title", "focus", "focus", "focus", "cta"]
    assert sc.title.endswith("#Shorts")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg がない")
def test_render_small_video(dg):
    from app.content import video

    try:
        video.font_path()
    except RuntimeError:
        pytest.skip("日本語フォントがない")
    sc = writer.script(dg, "ranking")
    meta = video.render(sc.scenes[:2], TMP / "v.mp4", scale=0.25)
    assert Path(meta["path"]).stat().st_size > 1000 and meta["duration"] > 2
