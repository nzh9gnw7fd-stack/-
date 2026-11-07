"""Playwright（ブラウザ操作）で note に投稿する。

note には記事投稿の公式 API がないため、ふつうのブラウザ操作を自動化する。
- ログインは手動で1回だけ行い、Cookie を out/note_storage.json に保存して使い回す（パスワードは保存しない）
- 既定は「下書き保存」まで。--publish を付けたときだけ有料設定をして公開する
- 画面の部品の指定は selectors.json にまとめてあるので、note の画面が変わったらそこを直す
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from . import config
from .generate import Article
from .render import article_html

log = logging.getLogger(__name__)

PASTE_JS = """([sel, html, text]) => {
  const el = document.querySelector(sel);
  if (!el) throw new Error('本文の入力欄が見つかりません: ' + sel);
  el.focus();
  const dt = new DataTransfer();
  dt.setData('text/html', html);
  dt.setData('text/plain', text);
  el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
}"""


def selectors() -> dict[str, Any]:
    return json.loads(config.SELECTORS_PATH.read_text(encoding="utf-8"))


def login() -> Path:
    """ブラウザを開いて手動でログインしてもらい、ログイン状態を保存する。"""
    from playwright.sync_api import sync_playwright

    sel = selectors()
    config.STORAGE_STATE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=config.CHROMIUM_PATH)
        ctx = browser.new_context(locale="ja-JP")
        page = ctx.new_page()
        page.goto(sel["login_url"])
        input("ブラウザで note にログインしたら、ここで Enter を押してください > ")
        ctx.storage_state(path=str(config.STORAGE_STATE))
        browser.close()
    config.STORAGE_STATE.chmod(0o600)
    return config.STORAGE_STATE


class PublishError(RuntimeError):
    pass


def post(article: Article, publish: bool = False, shots_dir: Path | None = None) -> str:
    """記事を note に入れて、編集画面（または公開後）の URL を返す。"""
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright

    if not config.STORAGE_STATE.exists():
        raise PublishError("ログイン状態がありません。先に `python -m note_auto login` を実行してください")

    sel = selectors()
    timeout = int(sel.get("timeout_ms", 30000))
    body_html, free_blocks = article_html(article.free_body, article.paid_body)
    plain = f"{article.free_body}\n\n{article.paid_body}"
    shots_dir = shots_dir or config.OUT_DIR / article.topic_id
    shots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.HEADLESS, executable_path=config.CHROMIUM_PATH)
        ctx = browser.new_context(storage_state=str(config.STORAGE_STATE), locale="ja-JP")
        ctx.set_default_timeout(timeout)
        page = ctx.new_page()

        def shot(name: str) -> None:
            try:
                page.screenshot(path=str(shots_dir / f"{name}.png"), full_page=True)
            except Exception:  # noqa: BLE001
                pass

        try:
            page.goto(sel["new_url"])
            page.wait_for_selector(sel["title"])
            if "login" in page.url:
                raise PublishError("ログインが切れています。`python -m note_auto login` をやり直してください")

            page.fill(sel["title"], article.title)
            page.wait_for_selector(sel["body"])
            page.evaluate(PASTE_JS, [sel["body"], body_html, plain])
            page.wait_for_timeout(1500)
            shot("1_editor")

            if not publish:
                page.get_by_role("button", name=sel["save_draft_text"]).click()
                page.wait_for_timeout(2500)
                shot("2_saved")
                return page.url

            page.get_by_role("button", name=sel["go_publish_text"]).click()
            page.wait_for_load_state("networkidle")
            shot("2_publish_settings")

            tag_input = page.locator(sel["hashtag_input"]).first
            for t in article.hashtags:
                tag_input.fill(t)
                tag_input.press("Enter")
                page.wait_for_timeout(300)

            page.get_by_text(sel["paid_label_text"], exact=True).first.click()
            price = page.locator(sel["price_input"]).first
            price.fill(str(article.price))

            # 有料ラインの位置: 無料部分の最後のブロックの直後
            buttons = page.get_by_role("button", name=sel["paid_line_button_text"])
            n = buttons.count()
            idx = free_blocks + int(sel.get("paid_line_offset", -1))
            if n == 0 or not 0 <= idx < n:
                shot("3_paid_line_error")
                raise PublishError(f"有料ラインのボタンが見つかりません（{n}個, 位置 {idx}）。下書きとして残っています")
            buttons.nth(idx).scroll_into_view_if_needed()
            buttons.nth(idx).click()
            page.wait_for_timeout(800)
            shot("3_before_submit")

            page.get_by_role("button", name=sel["submit_text"]).last.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2500)
            shot("4_published")
            return page.url
        except PWTimeout as e:
            shot("error")
            raise PublishError(f"画面の部品が見つからず時間切れになりました（selectors.json を確認）: {e}") from e
        finally:
            browser.close()
