import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../../config';
import { GameInput } from '../../core/input';
import { FONT } from '../../core/ui';
import { MEMBERS } from '../data';
import { playMusic } from '../music';
import { game, saveGame } from '../state';

export class EndingScene extends Phaser.Scene {
  private controls!: GameInput;
  private canLeave = false;

  constructor() {
    super('RpgEnding');
  }

  create(): void {
    const s = game.state;
    s.flags.cleared = true;
    saveGame(s);
    this.canLeave = false;
    this.cameras.main.setBackgroundColor('#0b1033');
    this.cameras.main.fadeIn(1500, 255, 255, 255);
    playMusic('title');

    const min = Math.floor(s.playMs / 60000);
    const party = s.party.map((m) => `${MEMBERS[m.id].name}  Lv ${m.level}`).join('\n');
    const lines = [
      '水の石を泉にもどすと――',
      '',
      'こんこんと、澄んだ水がわきだした。',
      'ハルナ村に、ふたたび笑顔がもどった。',
      '',
      '3人の名は、泉の守り手として',
      'いつまでも語りつがれたという。',
      '',
      '',
      '― 冒険の記録 ―',
      party,
      '',
      `戦った回数  ${s.battles} 回`,
      `歩いた歩数  ${s.steps} 歩`,
      `プレイ時間  ${min} 分`,
      '',
      '',
      'THE END',
      '',
      'Thank you for playing!',
    ].join('\n');
    const t = this.add.text(GAME_WIDTH / 2, GAME_HEIGHT + 20, lines, { fontFamily: FONT, fontSize: '24px', color: '#ffffff', align: 'center', lineSpacing: 10 }).setOrigin(0.5, 0);
    const end = GAME_HEIGHT / 2 - t.height + 60;
    this.tweens.add({
      targets: t, y: end, duration: 22000, ease: 'Linear',
      onComplete: () => {
        this.canLeave = true;
        this.add.text(GAME_WIDTH / 2, GAME_HEIGHT - 40, 'Space / クリックでタイトルへ', { fontFamily: FONT, fontSize: '16px', color: '#90caf9' }).setOrigin(0.5);
      },
    });
    this.controls = new GameInput(this);
    // 決定ボタン長押しで早送り
    this.input.on('pointerdown', () => (this.canLeave ? this.leave() : this.tweens.timeScale = 4));
    this.input.on('pointerup', () => (this.tweens.timeScale = 1));
  }

  update(): void {
    if (this.canLeave && this.controls.actionPressed) this.leave();
    else if (!this.canLeave) this.tweens.timeScale = this.controls.action ? 4 : this.input.activePointer.isDown ? 4 : 1;
  }

  private leave(): void {
    this.tweens.timeScale = 1;
    this.scene.start('RpgTitle');
  }
}
