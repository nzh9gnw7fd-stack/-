# ゲーム制作環境（GAME LAB）

**Vite + TypeScript + Phaser 4** によるブラウザゲームの開発環境です。
ジャンル別のサンプルと、どのゲームでも使える共通部品（入力・効果音・セーブ・会話など）が入っています。
サンプルをコピーして書き換えれば、自分のゲームの土台にできます。

## 始め方

Node.js 20 以上（推奨 22）が必要です。

```bash
cd game
npm install       # 初回のみ
npm run dev       # → http://localhost:5173 （保存すると自動で再読み込み）
```

| コマンド | 内容 |
|---|---|
| `npm run dev` | 開発サーバー（ホットリロード、デバッグパネル付き） |
| `npm run build` | 型チェック後、`dist/` に公開用ファイルを出力 |
| `npm run preview` | ビルド結果をローカルで確認 |
| `npm run typecheck` | 型チェックのみ |
| `npm test` | ロジックのテスト（Vitest） |

`dist/` はそのまま静的サイトとして公開できます（GitHub Pages、itch.io など）。

## 完成版 RPG「泉の石と岩喰いのヌシ」

`npm run dev` → http://localhost:5173/rpg.html （メニュー画面の下のボタンからも行けます）

枯れた村の泉を取り戻すため、剣士・魔法使い・僧侶の3人で洞窟のヌシに挑む、15〜30分ほどで遊べる短編 RPG です。

- 村・平原・洞窟の3マップ、宿屋・道具屋・宝箱・回復の泉
- ランダムエンカウントのターン制バトル（たたかう / スキル / どうぐ / ぼうぎょ / にげる）
- レベルアップと技の習得、装備の付け替え、セーブ / つづきから
- 8bit 風の BGM（その場で合成）、ボス戦、エンディング

| 操作 | キー |
|---|---|
| 移動 | 矢印キー / WASD（パッド・タッチも可） |
| 話す・調べる・決定 | Space / Enter / Z |
| メニュー・キャンセル | X / ESC（画面右上の MENU ボタンでも可） |

### 改造するには（`src/rpg/`）

| ファイル | 中身 |
|---|---|
| `data.ts` | キャラ・敵・技・道具・装備・お店・出現テーブル。**数値を変えるとバランス調整** |
| `maps.ts` | マップ（文字で描く）、人・宝箱・出口・イベントの配置 |
| `events.ts` | 会話やイベントの中身（村長の話、宿屋、ボス戦など） |
| `battle.ts` | バトルの計算（ダメージ式・敵の行動）。描画とは独立 |
| `state.ts` | セーブデータ・レベルアップ・装備の処理 |
| `scenes/` | タイトル・マップ・バトル・エンディングの画面 |
| `textures.ts` / `music.ts` | 仮の絵と BGM。画像や音声ファイルに差し替え可 |

`tests/rpg/` に、マップの到達チェックやボス戦の勝率シミュレーション（レベル8・良い装備でだいたい勝てるか）があるので、
バランスを変えたら `npm test` で確認できます。

## ジャンル別サンプル

| ジャンル | ファイル | 見どころ |
|---|---|---|
| トップダウン | `src/samples/CoinDashScene.ts` | ステートマシンで「待機→プレイ→結果」、ハイスコア保存 |
| アクション（横スクロール） | `src/samples/PlatformerScene.ts` | 文字で描くステージ→タイルマップ、踏みつけ、コヨーテタイム、パララックス背景 |
| シューティング | `src/samples/ShooterScene.ts` | 弾のオブジェクトプール、パーティクル爆発、無敵時間、自機狙い弾 |
| パズル（マッチ3） | `src/samples/Match3Scene.ts` + `src/logic/match3.ts` | 盤面ロジックと演出の分離、連鎖、async/await で演出を順番に |
| RPG フィールド | `src/samples/FieldScene.ts` | ノイズで島を自動生成、クリック移動（A* 経路探索）、NPC 会話、ミニマップ |
| ローグライク | `src/samples/RoguelikeScene.ts` + `src/logic/dungeon.ts` | ダンジョン自動生成、視界（FOV）、ターン制、敵の追跡 AI、階層 |
| 物理演算 | `src/samples/PhysicsScene.ts` | Matter.js（回転・摩擦・積み重ね）、軌道予測線 |
| ノベル / ADV | `src/samples/NovelScene.ts` + `src/data/novelScript.ts` | 分岐シナリオ、フラグ、文字送り、立ち絵 |
| 3D | `src/three/main.ts`（`3d.html`） | three.js、ライトと影、3人称カメラ、当たり判定 |

## 共通部品（`src/core/`）

| ファイル | できること |
|---|---|
| `input.ts` | **キーボード・ゲームパッド・タッチ（スマホの仮想スティック）** をまとめて扱う |
| `sfx.ts` | 効果音をその場で合成（ファイル不要）。`sfx.coin()` `sfx.jump()` `sfx.explode()` など |
| `save.ts` | セーブ / ロード（`saveData` / `loadData`）、ハイスコア |
| `stateMachine.ts` | 状態管理（画面の流れ、敵の AI など） |
| `dialogueBox.ts` | メッセージウィンドウ（文字送り・選択肢）。シナリオ処理は `logic/dialogue.ts` |
| `debugGui.ts` | 数値をスライダーで調整できるデバッグパネル（開発中 or URL に `?debug`） |
| `ui.ts` | ボタン、テキスト、「メニューへ戻る」、tween を await する `tweenAsync` |
| `textures.ts` | 仮の絵（図形）。同じキー名で画像を読み込めば差し替わる |
| `random.ts` | シード付き乱数（同じシードなら同じマップ） |

## 入っているライブラリ

| ライブラリ | 用途 |
|---|---|
| [Phaser 4](https://phaser.io/) | 2D ゲームエンジン本体。描画・アニメ・タイルマップ・Arcade 物理・Matter 物理・音・カメラ・パーティクル |
| [three.js](https://threejs.org/) | 3D 描画。`.glb` モデルの読み込みも可（`three/addons/loaders/GLTFLoader.js`） |
| [rot.js](https://ondras.github.io/rot.js/hp/) | ローグライク向け：ダンジョン生成、視界計算、経路探索（A*） |
| [simplex-noise](https://github.com/jwagner/simplex-noise.js) | 地形や雲などの自然な乱数（手続き生成） |
| [lil-gui](https://lil-gui.georgealways.com/) | デバッグ用の調整パネル |
| Vite / TypeScript / Vitest | 開発サーバー・型チェック・テスト |

## 自分のゲームを作るには

1. 近いジャンルのサンプルを `src/samples/` 内でコピーし、クラス名と `super('名前')` を変える
2. `src/main.ts` の `scene: [...]` に追加し、`src/scenes/MenuScene.ts` の `SAMPLES` にボタンを足す
3. ルールや計算は `src/logic/` に分けて書くと、`tests/` でテストできる

完全に1本のゲームにしたいときは、`main.ts` の `scene` を自分のシーンだけにすればメニューは出なくなります。

### 素材（画像・音・マップ）を使う

`public/assets/` に置いて、`src/scenes/BootScene.ts` の `preload()` で読み込みます。

```ts
this.load.image('player', 'assets/player.png');   // 'player' の仮の絵が差し替わる
this.load.spritesheet('hero', 'assets/hero.png', { frameWidth: 32, frameHeight: 32 });
this.load.audio('bgm', ['assets/bgm.ogg', 'assets/bgm.mp3']);
this.load.tilemapTiledJSON('stage1', 'assets/stage1.json');
```

- マップは無料エディタ [Tiled](https://www.mapeditor.org/) で作って JSON 書き出し → `this.make.tilemap({ key: 'stage1' })`
- 無料素材: [Kenney](https://kenney.nl/assets)（CC0、商用可）、[OpenGameArt](https://opengameart.org/)（ライセンスは素材ごとに確認）
- 効果音作成: [jsfxr](https://sfxr.me/)

## デバッグのコツ

- 開発中は右上にデバッグパネルが出ます（アクション / シューティング）。ジャンプ力などをその場で調整し、気に入った値をコードに書き戻します。
- ブラウザのコンソールで `game.scene.getScene('Shooter').score` のように中身を見られます。
- 当たり判定の枠を見るには `src/main.ts` の `arcade: { debug: true }`。

## 公開・配布

- **Web**: `npm run build` → `dist/` をアップロード（itch.io は zip にして「HTML」として公開）
- **スマホアプリ**: [Capacitor](https://capacitorjs.com/) で `dist/` を iOS / Android アプリに包める
- **PC アプリ**: [Electron](https://www.electronjs.org/) や [Tauri](https://tauri.app/) で包める
- **オンライン対戦**: [Colyseus](https://colyseus.io/) などのサーバーを追加すると可能（別途サーバーが必要）
