import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { loadHighScore } from '../logic/highScore';

export class TitleScene extends Phaser.Scene {
  constructor() {
    super('Title');
  }

  create(): void {
    const cx = GAME_WIDTH / 2;
    this.add.text(cx, GAME_HEIGHT * 0.35, 'COIN DASH', { fontSize: '64px', fontStyle: 'bold', color: '#ffd54f' }).setOrigin(0.5);
    this.add.text(cx, GAME_HEIGHT * 0.5, '矢印キー / WASD で移動して、制限時間内にコインを集めよう', { fontSize: '20px', color: '#ffffff' }).setOrigin(0.5);
    this.add.text(cx, GAME_HEIGHT * 0.58, `ハイスコア: ${loadHighScore()}`, { fontSize: '20px', color: '#b0bec5' }).setOrigin(0.5);

    const prompt = this.add.text(cx, GAME_HEIGHT * 0.75, 'SPACE / クリックでスタート', { fontSize: '24px', color: '#4fc3f7' }).setOrigin(0.5);
    this.tweens.add({ targets: prompt, alpha: 0.2, duration: 700, yoyo: true, repeat: -1 });

    const start = () => this.scene.start('Game');
    this.input.keyboard?.once('keydown-SPACE', start);
    this.input.once('pointerdown', start);
  }
}
