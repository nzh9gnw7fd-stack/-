# ゲーム制作環境

**Vite + TypeScript + Phaser 4** によるブラウザゲームの開発環境です。
サンプルとして、コインを集めるミニゲーム「COIN DASH」が入っています。

## 必要なもの

- Node.js 20 以上（推奨 22）

## 使い方

```bash
cd game
npm install       # 初回のみ
npm run dev       # 開発サーバー起動 → http://localhost:5173 （保存すると自動で再読み込み）
```

| コマンド | 内容 |
|---|---|
| `npm run dev` | 開発サーバー（ホットリロード） |
| `npm run build` | 型チェック後、`dist/` に公開用ファイルを出力 |
| `npm run preview` | ビルド結果をローカルで確認 |
| `npm run typecheck` | TypeScript の型チェックのみ |
| `npm test` | Vitest でロジックのテスト |

`dist/` の中身はそのまま静的サイトとして公開できます（GitHub Pages、itch.io など）。

## フォルダ構成

```
game/
├─ index.html          ゲームを表示する HTML
├─ public/assets/      画像・音声などの素材（assets/xxx.png として読み込める）
├─ src/
│  ├─ main.ts          Phaser の設定とシーン登録
│  ├─ config.ts        画面サイズなどの定数
│  ├─ scenes/          画面（シーン）ごとのコード
│  │  ├─ BootScene.ts    素材の読み込み
│  │  ├─ TitleScene.ts   タイトル画面
│  │  ├─ GameScene.ts    ゲーム本体
│  │  └─ ResultScene.ts  結果画面
│  └─ logic/           Phaser に依存しない純粋なロジック（テストしやすい）
└─ tests/              Vitest のテスト
```

## 開発のヒント

- **新しい画面を足す**: `src/scenes/` にシーンを作り、`src/main.ts` の `scene: [...]` に追加。`this.scene.start('名前')` で切り替え。
- **画像を使う**: `public/assets/player.png` に置き、`BootScene` の `preload()` で `this.load.image('player', 'assets/player.png')`。
- **当たり判定を見る**: `src/main.ts` の `arcade: { debug: true }` にすると当たり判定の枠が表示されます。
- **デバッグ**: 開発中はブラウザのコンソールで `game` から Phaser の状態を確認できます（例: `game.scene.getScene('Game').score`）。
- ルールや計算は `src/logic/` に分けておくと、`npm test` で動作を確かめられます。

## 参考

- Phaser 公式: https://phaser.io/
- API ドキュメント: https://docs.phaser.io/
