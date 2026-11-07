import json

import pytest

from note_auto import config, generate, render, store
from note_auto.generate import Article, Topic


@pytest.fixture(autouse=True)
def tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "out" / "state.json")
    monkeypatch.setattr(config, "PROFILE_PATH", tmp_path / "profile.md")
    topics = tmp_path / "topics.json"
    topics.write_text(json.dumps([{"id": "t1", "theme": "テーマ1"}, {"id": "t2", "theme": "テーマ2", "price": 50}]),
                      encoding="utf-8")
    monkeypatch.setattr(config, "TOPICS_PATH", topics)


def test_render_blocks_and_paid_line_position():
    free = "## はじめに\n\n読むと**できること**。\n\n- 手順A\n- 手順B"
    paid = "### 手順\n\n1. 録音する\n2. 要約する\n\n> 注意\n\n```\nprompt <x>\n```"
    html, n = render.article_html(free, paid)
    assert n == 3
    assert html.startswith("<h2>はじめに</h2><p>読むと<strong>できること</strong>。</p><ul><li>手順A</li>")
    assert "<h3>手順</h3><ol><li>録音する</li><li>要約する</li></ol>" in html
    assert "<blockquote><p>注意</p></blockquote>" in html
    assert "<pre><code>prompt &lt;x&gt;</code></pre>" in html


def test_render_escapes_html_and_keeps_links():
    assert render.to_html("<script>x</script> [公式](https://note.com/)") == (
        '<p>&lt;script&gt;x&lt;/script&gt; <a href="https://note.com/">公式</a></p>'
    )


def test_price_and_tags_cleanup():
    assert generate.clamp_price(50) == 100
    assert generate.clamp_price("980") == 980
    assert generate.clamp_price(999999) == 50000
    assert generate.clean_tags(["#AI", "＃仕事術", "AI", " 時短 術 "]) == ["AI", "仕事術", "時短術"]


def _fake_article(**kw):
    d = {"title": "タイトル", "free_body": "無料", "paid_body": "有料", "price": 300,
         "hashtags": ["#AI"], "promo_post": "告知"}
    d.update(kw)
    return d


def test_create_rewrites_once_then_approves(monkeypatch):
    calls = []

    def fake_call(system, user, schema, effort):
        calls.append(user)
        if "paid_body" in schema["properties"]:
            return _fake_article(title="改善版" if "指摘" in user else "初稿")
        return ({"score": 60, "safe": True, "issues": ["具体例が足りない"], "summary": ""} if len(calls) == 2
                else {"score": 85, "safe": True, "issues": [], "summary": ""})

    monkeypatch.setattr(generate, "_call_json", fake_call)
    a = generate.create(Topic(id="t1", theme="x", price=50))
    assert a.status == "approved"
    assert a.title == "改善版"
    assert a.price == 100  # 最低価格に補正
    assert "具体例が足りない" in calls[2]


def test_create_marks_unsafe_as_needs_review(monkeypatch):
    def fake_call(system, user, schema, effort):
        if "paid_body" in schema["properties"]:
            return _fake_article()
        return {"score": 95, "safe": False, "issues": ["根拠のない収益の約束"], "summary": ""}

    monkeypatch.setattr(generate, "_call_json", fake_call)
    assert generate.create(Topic(id="t1", theme="x")).status == "needs_review"


def test_store_flow_and_daily_limit():
    assert [t.id for t in store.pending_topics(store.load_topics())] == ["t1", "t2"]
    a = Article("t1", "題", "無料", "有料", 300, ["AI"], "告知", {"score": 80}, "approved")
    store.save_article(a)
    assert (config.OUT_DIR / "t1" / "preview.md").read_text(encoding="utf-8").count("ここから有料（300円）") == 1
    assert [t.id for t in store.pending_topics(store.load_topics())] == ["t2"]
    assert store.articles_with_status("approved") == ["t1"]
    store.record_post(store.load_article("t1"), "https://note.com/x/n/abc", published=True)
    assert store.posts_today() == 1
    assert store.load_article("t1").status == "posted"
    assert store.articles_with_status("approved") == []


def test_run_skips_post_when_not_approved(monkeypatch, capsys):
    from note_auto import __main__ as cli

    def fake_create(t):
        return Article(t.id, "題", "無料", "有料", 300, [], "告知", {"score": 40, "safe": True}, "needs_review")

    monkeypatch.setattr(generate, "create", fake_create)
    posted = []
    monkeypatch.setattr(cli, "_post_one", lambda i, p: posted.append(i))
    cli.main(["run", "--publish"])
    assert posted == []
    assert "品質チェック不合格" in capsys.readouterr().out
