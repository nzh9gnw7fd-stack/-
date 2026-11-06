# 手動データ置き場

ここに置いたファイルは、自動更新のたびに集計に取り込まれます。GitHub の画面の「Add file」から追加・編集できます。

- `*.txt` … 投稿テキスト。1件ずつ `---` の行か、空行2つで区切る
- `*.csv` … 対戦ログや大会結果。列は `played_at,deck,opponent,result,rank,author,format`（result は win / loss、played_at は `2026-11-06T12:00:00Z` 形式）
- `*.json` … `[{"text": "...", "author": "...", "posted_at": "...", "url": "..."}]`

ファイル名が `_` で始まるものは無視されます（下書き用）。
