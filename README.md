# SVWB メタトラッカー

『Shadowverse: Worlds Beyond』の環境（デッキの使用率と推移、推定勝率、相性、ランク帯ごとの流行）を、
SNS・ブログ・大会結果などの投稿から推定して、ほぼリアルタイムに見られる Web アプリ。

> 数値はすべて投稿からの**推定値**です。SNS の報告には偏りがあり（勝ったときほど投稿される、上位勢の声が大きい等）、
> 公式の統計ではありません。

## 起動

```bash
pip install -r requirements.txt
python cli.py demo            # 架空のデモデータを投入（画面確認用）
uvicorn app.main:app --reload # http://localhost:8000
```

## 仕組み

```
 データ源                    抽出                         集計                   表示
 ─────────                  ─────                        ─────                  ─────
 X API（任意・有料）  ┐      Claude（構造化出力）         使用率の推移           ダッシュボード
 RSS/Atom（ブログ等） ├→ posts →  ↓ 失敗/未設定なら   → matches      → 推定勝率+信頼区間 → （60秒ごと自動更新）
 手動（テキスト/CSV/JSON）┘    ルールベース抽出            deck_reports   相性表 / ランク帯別
```

| ファイル | 役割 |
|---|---|
| `archetypes.json` | クラス・ランク・**アーキタイプ辞書**（表記ゆれ、キーカード）。パック更新ごとに編集する |
| `app/sources/` | `x_api.py`（X API v2 recent search）、`rss.py`、`manual.py`（貼り付け/CSV/JSON）、`demo.py`（架空データ） |
| `app/extract/rules.py` | 正規表現と辞書による抽出（無料） |
| `app/extract/llm.py` | Claude による抽出。デッキ名は JSON Schema の enum で辞書の正規名に限定 |
| `app/aggregate.py` | 集計（偏りへの対策は下記） |
| `app/main.py` | FastAPI の API とダッシュボード配信、定期収集 |
| `static/` | ダッシュボード（Chart.js は同梱） |

### 偏りへの対策

1. **両視点で数える**: 「A で B に勝った」は A の勝ちと B の負けの両方として数える。勝ち報告に偏っていても、
   全体の勝率は 50% になり、偏りがある程度打ち消される。
2. **投稿者ごとの上限**: 1人が1日に寄与できる重みを `SVWB_AUTHOR_DAILY_CAP`（既定 20 試合分）までにする。
3. **少数サンプルの補正**: 勝率は Beta(k,k) 事前分布で 50% 側に寄せた値を表示（`SVWB_PRIOR_K`、既定 10）。
   生の勝率には Wilson の 95% 信頼区間を付ける。
4. **連勝報告は勝率に使わない**（使用率のみに使う）。「〇〇多すぎ」のような愚痴は相手デッキの使用率シグナルとして使う。

## 無料で自動更新する（GitHub Actions + GitHub Pages）

公開リポジトリなら、GitHub Actions と GitHub Pages はどちらも無料。30分ごとに次の流れで自動更新される。

```
GitHub Actions（30分ごと）
  ├ archive/*.jsonl（これまでの投稿）から DB を作り直す
  ├ manual/ のファイルを取り込む（GitHub の画面から追加できる）
  ├ Mastodon / Misskey / Bluesky / RSS から新着を取得 → archive/ に追記してコミット
  ├ ルールで抽出・集計
  └ site/index.html を GitHub Pages に公開（開いたままのページも10分ごとに読み直す）
```

| データ源 | 費用 | 設定 |
|---|---|---|
| Mastodon（mstdn.jp・fedibird.com のハッシュタグ） | 無料・登録不要 | `sources.json` |
| Misskey（misskey.io のハッシュタグ） | 無料・登録不要 | `sources.json` |
| Bluesky 検索 | 無料（アカウントのアプリパスワード推奨） | Secrets: `BSKY_HANDLE` / `BSKY_APP_PASSWORD` |
| RSS / Atom（ブログ、note、YouTube、Google ニュース） | 無料 | `sources.json` の `rss.feeds` |
| 手動（大会結果 CSV、投稿テキスト） | 無料 | `manual/` にファイルを置く |
| X API / Claude 抽出 | 有料（任意） | Secrets: `X_BEARER_TOKEN` / `ANTHROPIC_API_KEY` |

### 最初の設定（1回だけ）

1. このリポジトリを **Public** で GitHub に置く
2. Settings → Pages → Build and deployment の Source を **GitHub Actions** にする
3. Actions タブ → update-site → **Run workflow** で初回を実行
4. 数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` で見られる
5. （任意）Bluesky の無料アカウントで Settings → Privacy and security → App passwords からパスワードを作り、
   リポジトリの Settings → Secrets and variables → Actions に `BSKY_HANDLE`（例: `name.bsky.social`）と `BSKY_APP_PASSWORD` を登録

注意:
- 投稿者のハンドルはハッシュ化して保存し、サイトには本文の先頭90文字と元投稿へのリンクだけを出す
- 公開リポジトリで60日間まったく動きがないと、GitHub がスケジュール実行を止めることがある（Actions タブから再開できる）
- 抽出は無料のルールベース。書き方が独特な投稿は取りこぼすので、`archetypes.json` の略称を増やすと精度が上がる

## データ源の設定（環境変数）

| 変数 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | 設定すると Claude で抽出する（未設定ならルールベース） |
| `SVWB_LLM_MODEL` | 抽出に使うモデル（既定 `claude-opus-5-5`）。量が多いときは `claude-haiku-5-5` にすると安くなる |
| `SVWB_LLM_EFFORT` | 既定 `low` |
| `X_BEARER_TOKEN` | X API v2 の Bearer Token（Basic プラン以上が必要）。設定すると定期収集する |
| `SVWB_X_QUERY` | X の検索クエリ |
| `SVWB_RSS_FEEDS` | カンマ区切りの RSS/Atom URL |
| `SVWB_SOCIAL` | `on` で `sources.json` の SNS・RSS から収集（Actions では on） |
| `SVWB_POLL_MINUTES` | 収集間隔（既定 30 分） |

X のスクレイピングは利用規約違反になるため実装していません。他サイトから取り込むときも、各サイトの規約と robots.txt に従ってください。

## CLI

```bash
python cli.py import posts.txt    # .txt（--- 区切り）/ .csv / .json を取り込み
python cli.py collect             # X / RSS から1回収集
python cli.py reextract           # 辞書を更新したあと、全投稿を抽出し直す
python cli.py snapshot out.html   # サーバーなしで見られる静的 HTML に書き出す
python cli.py reset               # DB を削除
python -m pytest -q tests
```

CSV の列: `played_at,deck,opponent,result,rank,author,format`（result は `win` / `loss`）

## 次にやること（候補）

- `archetypes.json` のキーカード欄を埋める（第10弾「ニーゲルヘリア神殺事件」環境のデッキ名は登録済み。キーカードを埋めると、デッキコードからの判定ができるようになる）
- デッキコード / デッキ共有サイトの URL からカードリストを取得して `Catalog.from_cards` で判定する
- 抽出結果を画面から修正できるようにする（修正データは評価セットにもなる）
- 公開する場合は認証付きの取り込み API とホスティング（例: Fly.io / Render ＋ SQLite→Postgres）
