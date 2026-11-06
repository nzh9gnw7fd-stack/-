import os
import tempfile
from pathlib import Path

os.environ.setdefault("SVWB_LLM", "off")

from app import aggregate as agg  # noqa: E402
from app import pipeline  # noqa: E402
from app.archetypes import catalog  # noqa: E402
from app.db import connect  # noqa: E402
from app.extract import rules  # noqa: E402
from app.sources import manual  # noqa: E402

cat = catalog()


def ex(text):
    return rules.extract(cat, text)


def test_single_match_with_using():
    e = ex("兎ビショ使用 vs キマイラウィッチ 勝ち")
    assert [(m.deck, m.opponent, m.result) for m in e.matches] == [("兎ビショップ", "スペルキマイラウィッチ", "win")]


def test_multi_line_log_and_rank():
    e = ex("今日の戦績（証拠ロイ）\nvs ミッドナイメア ○\nvs DDエルフ ×\nマスター帯")
    assert [(m.deck, m.opponent, m.result, m.rank) for m in e.matches] == [
        ("証拠ロイヤル", "ミッドレンジナイトメア", "win", "マスター"),
        ("証拠ロイヤル", "ダストデイズエルフ", "loss", "マスター"),
    ]


def test_record_report():
    e = ex("コンボEでマスター到達！15勝5敗")
    assert not e.matches
    r = e.reports[0]
    assert (r.deck, r.rank, r.wins, r.losses) == ("コンボエルフ", "マスター", 15, 5)


def test_grandmaster_not_master():
    assert ex("融合ネメでGM到達 20勝10敗").reports[0].rank == "グランドマスター"


def test_streak_not_used_for_winrate():
    r = ex("守護ビショップで10連勝").reports[0]
    assert r.deck == "守護ビショップ" and r.wins is None


def test_complaint_counts_as_opponent_sighting():
    e = ex("海賊ロイヤルに負けた")
    assert not e.matches and e.reports[0].deck == "海賊ロイヤル"


def test_unlimited_and_noise():
    assert ex("アンリミ スペウィ使用 vs ランプドラゴン 負け").format == "unlimited"
    assert ex("ガチャ爆死した").empty


def test_resolve_aliases():
    assert cat.resolve_archetype("ＡＦネメ") == "AFネメシス"
    assert cat.resolve_archetype("謎のドラゴン") == "その他ドラゴン"
    assert cat.resolve_archetype("キマイラW") == "スペルキマイラウィッチ"
    assert cat.resolve_archetype("スペル秘術") == "スペル秘術ウィッチ"
    assert cat.resolve_archetype("スペウィ") == "スペルウィッチ"


def test_formats_split():
    assert "兎ビショップ" in cat.archetype_names("rotation")
    assert "兎ビショップ" not in cat.archetype_names("unlimited")
    assert "テンポエルフ" in cat.archetype_names("unlimited")


def test_similar_names_prefer_longest():
    e = ex("スペルキマイラウィッチ使用 vs スペル秘術ウィッチ 勝ち")
    assert (e.matches[0].deck, e.matches[0].opponent) == ("スペルキマイラウィッチ", "スペル秘術ウィッチ")


def test_wilson_and_shrink():
    lo, hi = agg.wilson(50, 100)
    assert lo < 0.5 < hi and round(lo, 2) == 0.40
    assert agg.shrink(3, 3, k=10) < 0.6


def test_pipeline_both_perspectives_balance_to_50pct():
    with tempfile.TemporaryDirectory() as d:
        conn = connect(Path(d) / "t.db")
        csv = "played_at,deck,opponent,result,rank,author\n" + "\n".join(
            f"2026-11-0{1 + i % 5}T10:00:00Z,兎ビショップ,スペルキマイラウィッチ,{'win' if i % 4 else 'loss'},マスター,@u{i}"
            for i in range(40)
        )
        pipeline.store_posts(conn, manual.from_csv(csv))
        conn.commit()
        f = agg.Filters(days=60, end=__import__("datetime").datetime(2026, 11, 7, tzinfo=agg.timezone.utc))
        stats = {d["deck"]: d for d in agg.deck_stats(conn, f)}
        assert stats["兎ビショップ"]["winrate_raw"] == 0.75
        assert stats["スペルキマイラウィッチ"]["winrate_raw"] == 0.25
        m = agg.matchups(conn, f)
        assert m["grid"][0][1]["games"] == 40


def test_llm_response_parsing(monkeypatch):
    import json
    from types import SimpleNamespace

    from app.extract import llm

    payload = {"posts": [
        {"index": 0, "format": "rotation",
         "matches": [{"deck": "兎ビショップ", "opponent": "融合ネメシス", "result": "win",
                      "rank": "グランドマスター", "confidence": 0.9}], "reports": []},
        {"index": 1, "format": "rotation", "matches": [],
         "reports": [{"deck": "ミッドレンジナイトメア", "rank": None, "wins": None, "losses": None, "confidence": 0.6}]},
        {"index": 9, "format": "rotation", "matches": [], "reports": []},
    ]}
    sent = {}

    class FakeMessages:
        def create(self, **kw):
            sent.update(kw)
            return SimpleNamespace(stop_reason="end_turn",
                                   content=[SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))])

    monkeypatch.setattr(llm, "_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    out = llm.extract_batch(cat, ["a", "b", "c"])
    assert out[0].matches[0].opponent == "融合ネメシス"
    assert out[1].reports[0].deck == "ミッドレンジナイトメア"
    assert out[2].empty
    schema = sent["output_config"]["format"]["schema"]
    assert "その他ドラゴン" in schema["properties"]["posts"]["items"]["properties"]["matches"]["items"]["properties"]["deck"]["enum"]


def test_upper_ranks():
    assert ex("兎ビショでLEGEND到達 20勝9敗").reports[0].rank == "LEGEND"
    assert ex("融合ネメ使用 vs 海賊ロイ 勝ち beyond帯").matches[0].rank == "BEYOND"
    assert ex("証拠ロイでエピック帯 12勝8敗").reports[0].rank == "EPIC"
    assert ex("テンポE使用 ULTIMATE vs 兎ビショ ○").matches[0].rank == "ULTIMATE"
    # ゲーム名・レアリティ名はランクと誤認しない
    assert ex("シャドバビヨンド 兎ビショ使用 vs キマイラW 勝ち").matches[0].rank is None
    assert ex("#ShadowverseWorldsBeyond 融合ネメ使用 vs 海賊ロイ 勝ち").matches[0].rank is None
    assert ex("レジェンド引いた！兎ビショ使用 vs キマイラW 勝ち").matches[0].rank is None
    assert ex("Worlds Beyond legendary 融合ネメ使用 vs 海賊ロイ 勝ち").matches[0].rank is None
    assert cat.resolve_rank("legend") == "LEGEND"


def test_social_parsers():
    from app.sources import social

    ma = social.parse_mastodon([
        {"id": "1", "uri": "https://mstdn.jp/users/a/statuses/1", "url": "https://mstdn.jp/@a/1",
         "created_at": "2026-11-06T05:40:12.345Z", "visibility": "public",
         "content": "<p>兎ビショ使用<br>vs キマイラW 勝ち <a href=\"x\">#シャドバ</a></p>", "account": {"acct": "a"}},
        {"id": "2", "uri": "u2", "url": "u2", "created_at": "2026-11-06T05:40:12Z", "visibility": "public",
         "content": "", "reblog": {"id": "1"}, "account": {"acct": "b@x"}},
    ], "mstdn.jp")
    assert len(ma) == 1 and ma[0].posted_at == "2026-11-06T05:40:12Z"
    assert ma[0].text.startswith("兎ビショ使用\nvs キマイラW") and ma[0].author.startswith("u_")
    assert rules.extract(cat, ma[0].text).matches[0].opponent == "スペルキマイラウィッチ"

    mi = social.parse_misskey([
        {"id": "9x", "createdAt": "2026-11-06T01:02:03.000Z", "text": "融合ネメでLEGEND帯 10勝4敗",
         "visibility": "public", "user": {"username": "c", "host": None}},
        {"id": "9y", "createdAt": "2026-11-06T01:02:03.000Z", "text": None, "user": {"username": "d"}},
    ], "misskey.io")
    assert [p.url for p in mi] == ["https://misskey.io/notes/9x"]

    bs = social.parse_bluesky([{
        "uri": "at://did:plc:abc/app.bsky.feed.post/3kxyz", "indexedAt": "2026-11-06T02:00:00.000Z",
        "author": {"handle": "e.bsky.social", "did": "did:plc:abc"},
        "record": {"text": "海賊ロイでマスター到達", "createdAt": "2026-11-06T01:59:00.000Z"},
    }])
    assert bs[0].url == "https://bsky.app/profile/e.bsky.social/post/3kxyz"
    assert bs[0].posted_at == "2026-11-06T01:59:00Z"


def test_archive_roundtrip():
    from app import archive
    from app.sources import RawPost

    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        posts = [RawPost("mastodon", "a", "t1", "2026-10-31T23:00:00Z", "u_1"),
                 RawPost("mastodon", "b", "t2", "2026-11-01T01:00:00Z", "u_2")]
        known: set = set()
        assert archive.append(p, posts, known) == 2
        assert archive.append(p, posts, known) == 0  # 重複は追記しない
        assert sorted(f.name for f in p.iterdir()) == ["2026-10.jsonl", "2026-11.jsonl"]
        assert [x.external_id for x in archive.load(p)] == ["a", "b"]
