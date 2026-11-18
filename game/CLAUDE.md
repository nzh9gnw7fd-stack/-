# game/ — ブラウザゲーム開発環境

- 技術: Vite 8 + TypeScript (strict) + Phaser 4、3D は three.js（`3d.html` → `src/three/main.ts`）
- 構成: `src/core/` 共通部品、`src/logic/` Phaser に依存しない純粋ロジック（Vitest でテスト）、`src/samples/` ジャンル別サンプルシーン、`src/data/` シナリオ等のデータ
- 入力は `GameInput`（core/input.ts）を使う。キーボード・ゲームパッド・タッチを一括で扱い、「押した瞬間」は keydown イベントから取るので取りこぼさない
- 完成版 RPG は `rpg.html` → `src/rpg/main.ts`（独立した Phaser.Game）。データ `data.ts`、マップ `maps.ts`、イベント `events.ts`、計算 `battle.ts`/`state.ts` は描画から独立しテスト済み（`tests/rpg/`）。バランスを変えたらボス勝率テストを確認
- 新しいシーンは `src/main.ts` の `scene` 配列と `MenuScene` の `SAMPLES` に登録
- 確認: `npm run typecheck && npm test && npm run build`、動作は `npm run dev`（開発中は `window.game` で状態を見られる）

## Phaser 4 での注意（Phaser 3 との違い）
- `group.children` はネイティブの Set。`.each()` は無いので `group.getChildren()` を for..of で回す
- `GeometryMask` は Canvas 専用。WebGL ではマスクに `filters.internal.addMask()` を使う（サンプルでは「フタ」で代用）
- `scene.events.on('update', ...)` はシーンを restart しても残るので使わず、`update()` に書く
- `TimerEvent.delay` は読み取り専用。間隔を変えるときはタイマーを作り直す
- `createLayer()` は `TilemapLayer | TilemapGPULayer` を返す。タイル単位の操作が必要なら `as Phaser.Tilemaps.TilemapLayer`
