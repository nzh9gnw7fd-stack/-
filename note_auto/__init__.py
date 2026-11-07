"""note の有料記事を自動で書いて投稿する仕組み。

流れ: テーマ一覧（topics.json）→ Claude で執筆 → Claude で品質チェック（不合格なら書き直し）
→ HTML に変換 → Playwright で note に下書き保存（--publish なら有料設定をして公開）。
"""
