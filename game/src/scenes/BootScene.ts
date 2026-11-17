import Phaser from 'phaser';

/**
 * アセットの読み込みを担当するシーン。
 * 画像や音声は public/assets/ に置き、ここで this.load.image('key', 'assets/xxx.png') のように読み込む。
 * サンプルでは画像を用意しなくても動くよう、図形からテクスチャを生成している。
 */
export class BootScene extends Phaser.Scene {
  constructor() {
    super('Boot');
  }

  preload(): void {
    // 例: this.load.image('player', 'assets/player.png');
  }

  create(): void {
    this.makeTexture('player', 40, 40, (g) => {
      g.fillStyle(0x4fc3f7).fillRoundedRect(0, 0, 40, 40, 8);
      g.fillStyle(0xffffff).fillCircle(13, 15, 5).fillCircle(27, 15, 5);
      g.fillStyle(0x1d2033).fillCircle(14, 16, 2).fillCircle(28, 16, 2);
    });
    this.makeTexture('coin', 20, 20, (g) => {
      g.fillStyle(0xffd54f).fillCircle(10, 10, 10);
      g.fillStyle(0xffecb3).fillCircle(7, 7, 3);
    });
    this.scene.start('Title');
  }

  private makeTexture(key: string, w: number, h: number, draw: (g: Phaser.GameObjects.Graphics) => void): void {
    const g = this.make.graphics({ x: 0, y: 0 }, false);
    draw(g);
    g.generateTexture(key, w, h);
    g.destroy();
  }
}
