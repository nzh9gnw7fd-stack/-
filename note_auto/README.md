# note 有料記事 自動執筆・投稿

テーマの一覧を渡すと、Claude が有料記事（無料部分＋有料部分）を書き、別の Claude が読者の目で採点し、
合格した記事だけを note に投稿します。

```
topics.json（テーマ一覧）
   │
   ▼
① 執筆（Claude）── タイトル / 無料部分 / 有料部分 / 価格 / ハッシュタグ / X 告知文
   │
   ▼
② 品質チェック（Claude）── 具体性・無料部分の質・価格との釣り合い・誇大表現や捏造がないか（100点満点）
   │   不合格 → 指摘を渡して1回書き直す → まだ不合格なら needs_review（投稿しない。人が直して approve）
   ▼
③ 投稿（Playwright でブラウザ操作）── 既定は下書き保存。--publish で有料設定（価格・有料ライン・タグ）をして公開
   │
   ▼
④ 告知文を表示（X に貼る）
```

| ファイル | 役割 |
|---|---|
| `generate.py` | 執筆と採点のプロンプト、書き直しのループ |
| `render.py` | Markdown → note のエディタに貼れる HTML。有料ラインの位置（無料部分のブロック数）も出す |
| `publisher.py` | note へのログイン状態の保存と、下書き保存・公開の自動操作 |
| `selectors.json` | note の画面の部品の指定。**note の画面が変わって失敗したらここを直す** |
| `store.py` | テーマ一覧、生成済み記事（`out/<ID>/`）、投稿履歴（`out/state.json`） |
| `topics.example.json` / `profile.example.md` | テーマとプロフィールの見本 |

## 使い方（自分の PC で動かす。おすすめ）

```bash
pip install -r requirements.txt playwright
python -m playwright install chromium
export ANTHROPIC_API_KEY=sk-ant-...

cp note_auto/topics.example.json note_auto/topics.json   # テーマを書く
cp note_auto/profile.example.md note_auto/profile.md     # 書き手の経験・実績を書く（ここにない実績は記事に書かれない）

python -m note_auto login        # ブラウザが開くので note にログイン → Enter
python -m note_auto generate     # 1本書いて採点。out/<ID>/preview.md で中身を確認できる
python -m note_auto post         # 合格した記事を note に「下書き保存」
python -m note_auto post --publish   # 有料記事として公開する
```

毎日自動で動かすなら、cron（Mac/Linux）やタスクスケジューラ（Windows）で次を1日1回実行します。

```bash
cd /path/to/repo && python -m note_auto run --publish
```

`run` は「承認済みが残っていればそれを投稿、なければ1本書いて合格なら投稿」をします。

### テーマ（topics.json）の書き方

```json
{
  "id": "001-chatgpt-meeting-notes",
  "theme": "生成AIで会議の議事録づくりを10分で終わらせる手順",
  "reader": "毎週の議事録に1時間以上かけている会社員",
  "angle": "録音→文字起こし→要約→ToDo抽出の流れと、そのまま使えるプロンプト",
  "price": 480,
  "notes": "自分の部署で半年運用している。最初は要約が長すぎて失敗した"
}
```

売れる記事にする一番の近道は `notes` と `profile.md` に**自分の実体験・失敗談・数字**を書くことです。
ここが空だと一般論の記事になり、品質チェックで落ちやすく、買われにくくなります。

### 不合格（needs_review）の記事

`out/<ID>/article.json` の `free_body` / `paid_body` を直してから:

```bash
python -m note_auto approve <ID>
python -m note_auto post <ID> --publish
```

## GitHub Actions で動かす（任意）

このリポジトリは公開なので、**有料部分の原稿はコミットしない**作りにしてあります（`out/` は .gitignore 済み、Actions ではキャッシュにだけ保存）。

1. 自分の PC で `python -m note_auto login` をして、`base64 -w0 note_auto/out/note_storage.json` の出力をコピー
2. Settings → Secrets and variables → Actions に登録
   - `ANTHROPIC_API_KEY`
   - `NOTE_STORAGE_STATE_B64`（1 の出力）
   - `NOTE_TOPICS_JSON`（topics.json の中身）
   - `NOTE_PROFILE`（任意。profile.md の中身）
3. Actions → note-auto → Run workflow（まず publish をオフで下書き保存を試す）
4. 問題なければ `.github/workflows/note-auto.yml` の `schedule` のコメントを外す

ログイン Cookie の期限が切れたら 1〜2 をやり直します。海外の IP からのログインになるため、note 側で追加の確認が出ることがあります。

## 設定（環境変数）

| 変数 | 既定 | 内容 |
|---|---|---|
| `NOTE_MODEL` | `claude-opus-5-5` | 執筆・採点に使うモデル |
| `NOTE_EFFORT` / `NOTE_REVIEW_EFFORT` | `high` / `medium` | 執筆・採点の思考の深さ |
| `NOTE_PASS_SCORE` | `75` | 合格点 |
| `NOTE_MAX_REWRITES` | `1` | 書き直しの最大回数 |
| `NOTE_DAILY_LIMIT` | `1` | 1日に公開する上限 |
| `NOTE_HEADLESS` | `1` | `0` にするとブラウザ画面を表示して動く（失敗の原因を見るとき） |

費用の目安: 1本あたり Claude API で数十円〜100円程度（執筆＋採点、書き直しがあると増える）。

## 注意

- **note には記事投稿の公式 API がありません。** ブラウザ操作の自動化なので、note の画面が変わると動かなくなります。
  失敗したときは `out/<ID>/*.png` のスクリーンショットを見て `selectors.json` を直してください（`NOTE_HEADLESS=0` で画面を見ながら試せます）。
- この仕組みは note.com に接続できない環境で作ったため、**実際の note の画面ではまだ試していません**。
  最初は必ず下書き保存（`post` を `--publish` なし）で試し、note 上で本文・見出し・有料ラインの位置を確認してください。
  有料ラインがずれる場合は `selectors.json` の `paid_line_offset` を調整します。
- 自動投稿や AI で量産した低品質な有料記事は、note の規約・ガイドラインに触れてアカウント停止になるおそれがあります。
  公開は1日1本までにしてあります（`NOTE_DAILY_LIMIT`）。最初のうちは公開前に `preview.md` を読むことをおすすめします。
- 「誰でも稼げる」のような根拠のない表現や、やっていない実績を書くと景品表示法などの問題になり得ます。
  プロンプトと採点で防いでいますが、最終的な責任は投稿者にあります。
- `out/note_storage.json` はログイン状態そのものです。人に渡したりコミットしたりしないでください。
