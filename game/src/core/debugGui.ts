import type Phaser from 'phaser';
import GUI from 'lil-gui';

/**
 * 数値をスライダーでいじれるデバッグパネル（lil-gui）。
 * 開発サーバー（npm run dev）か、URL に ?debug を付けたときだけ表示される。
 *
 *   const gui = createDebugGui(this, 'Player');
 *   gui?.add(params, 'jumpSpeed', 200, 1000);
 */
export function createDebugGui(scene: Phaser.Scene, title: string): GUI | null {
  const enabled = import.meta.env.DEV || new URLSearchParams(location.search).has('debug');
  if (!enabled) return null;
  const gui = new GUI({ title: `${title}（デバッグ）` });
  gui.close();
  scene.events.once('shutdown', () => gui.destroy());
  return gui;
}
