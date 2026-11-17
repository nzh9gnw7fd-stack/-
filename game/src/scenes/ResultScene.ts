import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { saveHighScore } from '../logic/highScore';

export class ResultScene extends Phaser.Scene {
  constructor() {
    super('Result');
  }

  create(data: { score: number }): void {
    const cx = GAME_WIDTH / 2;
    const isNew = saveHighScore(data.score);
    this.add.text(cx, GAME_HEIGHT * 0.35, 'TIME UP!', { fontSize: '56px', fontStyle: 'bold', color: '#ffffff' }).setOrigin(0.5);
    this.add.text(cx, GAME_HEIGHT * 0.5, `SCORE: ${data.score}`, { fontSize: '36px', color: '#ffd54f' }).setOrigin(0.5);
    if (isNew) this.add.text(cx, GAME_HEIGHT * 0.58, 'NEW RECORD!', { fontSize: '24px', color: '#ff8a65' }).setOrigin(0.5);
    this.add.text(cx, GAME_HEIGHT * 0.75, 'SPACE / クリックでタイトルへ', { fontSize: '22px', color: '#4fc3f7' }).setOrigin(0.5);

    const back = () => this.scene.start('Title');
    this.input.keyboard?.once('keydown-SPACE', back);
    this.input.once('pointerdown', back);
  }
}
