import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { sfx } from './sfx';

export const FONT = '"Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif';

export function text(scene: Phaser.Scene, x: number, y: number, str: string, size = 20, color = '#ffffff'): Phaser.GameObjects.Text {
  return scene.add.text(x, y, str, { fontFamily: FONT, fontSize: `${size}px`, color }).setScrollFactor(0);
}

/** クリックできるボタン */
export function button(
  scene: Phaser.Scene, x: number, y: number, w: number, h: number,
  label: string, onClick: () => void, sub?: string,
): Phaser.GameObjects.Container {
  const bg = scene.add.rectangle(0, 0, w, h, 0x2b3050).setStrokeStyle(2, 0x4fc3f7);
  const title = scene.add.text(0, sub ? -12 : 0, label, { fontFamily: FONT, fontSize: '20px', color: '#ffffff', fontStyle: 'bold' }).setOrigin(0.5);
  const parts: Phaser.GameObjects.GameObject[] = [bg, title];
  if (sub) parts.push(scene.add.text(0, 14, sub, { fontFamily: FONT, fontSize: '13px', color: '#b0bec5' }).setOrigin(0.5));
  const c = scene.add.container(x, y, parts).setScrollFactor(0).setDepth(900);
  bg.setInteractive({ useHandCursor: true })
    .on('pointerover', () => bg.setFillStyle(0x3d4470))
    .on('pointerout', () => bg.setFillStyle(0x2b3050))
    .on('pointerdown', (_p: Phaser.Input.Pointer, _x: number, _y: number, e: Phaser.Types.Input.EventData) => {
      e.stopPropagation();
      sfx.select();
      onClick();
    });
  return c;
}

/** 左下に「メニューへ戻る」ボタンと、操作説明を出す。ESC でも戻れる。 */
export function addSampleChrome(scene: Phaser.Scene, help: string): void {
  const back = () => scene.scene.start('Menu');
  const t = text(scene, 10, GAME_HEIGHT - 28, '← MENU (ESC)', 16, '#90a4ae').setDepth(1000).setInteractive({ useHandCursor: true });
  t.on('pointerdown', (_p: Phaser.Input.Pointer, _x: number, _y: number, e: Phaser.Types.Input.EventData) => {
    e.stopPropagation();
    back();
  });
  scene.input.keyboard?.once('keydown-ESC', back);
  text(scene, GAME_WIDTH - 10, GAME_HEIGHT - 28, help, 14, '#90a4ae').setOrigin(1, 0).setDepth(1000);
}

/** tween を Promise として待てるようにする（演出を順番に流したいとき用） */
export function tweenAsync(scene: Phaser.Scene, config: Phaser.Types.Tweens.TweenBuilderConfig): Promise<void> {
  return new Promise((resolve) => scene.tweens.add({ ...config, onComplete: () => resolve() }));
}
