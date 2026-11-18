import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../../config';
import { GameInput } from '../../core/input';
import { isMuted, setMuted } from '../../core/sfx';
import { FONT } from '../../core/ui';
import { playMusic, refreshMusic, stopMusic } from '../music';
import { game, loadGame, newGame } from '../state';
import { SelectList, UIStack, type ListItem } from '../ui';

export class TitleScene extends Phaser.Scene {
  private controls!: GameInput;
  private ui!: UIStack;
  private started = false;

  constructor() {
    super('RpgTitle');
  }

  create(): void {
    this.started = false;
    // 夜空と山並み
    const g = this.add.graphics();
    g.fillStyle(0x0b1033).fillRect(0, 0, GAME_WIDTH, GAME_HEIGHT);
    for (let i = 0; i < 120; i++) g.fillStyle(0xffffff, Math.random() * 0.8 + 0.2).fillRect(Math.random() * GAME_WIDTH, Math.random() * 380, 2, 2);
    g.fillStyle(0x1c2350).fillTriangle(-100, 600, 200, 300, 500, 600).fillTriangle(250, 600, 560, 260, 900, 600);
    g.fillStyle(0x10163a).fillRect(0, 520, GAME_WIDTH, 80);
    g.fillStyle(0x4dd0e1, 0.9).fillCircle(640, 110, 34);

    const title = this.add.text(GAME_WIDTH / 2, 150, '泉の石と\n岩喰いのヌシ', { fontFamily: FONT, fontSize: '56px', color: '#ffffff', fontStyle: 'bold', align: 'center', stroke: '#1a237e', strokeThickness: 8 })
      .setOrigin(0.5).setAlpha(0);
    this.tweens.add({ targets: title, alpha: 1, y: 170, duration: 1200, ease: 'Cubic.Out' });
    this.add.text(GAME_WIDTH / 2, 268, '- A Tiny RPG -', { fontFamily: FONT, fontSize: '18px', color: '#90caf9' }).setOrigin(0.5);

    this.controls = new GameInput(this);
    this.ui = new UIStack();
    const save = loadGame();
    const items: ListItem[] = [
      { label: 'はじめから', onSelect: () => this.start(newGame()) },
      { label: 'つづきから', disabled: !save, onSelect: () => save && this.start(save) },
      { label: `サウンド: ${isMuted() ? 'OFF' : 'ON'}`, onSelect: () => this.toggleSound(list, items) },
      { label: 'GAME LAB にもどる', onSelect: () => { stopMusic(); window.location.href = './index.html'; } },
    ];
    const list = new SelectList(this, GAME_WIDTH / 2 - 130, 320, 260, items);
    if (save) list.index = 1;
    list.setItems(items);
    this.ui.push(list);
    this.add.text(GAME_WIDTH / 2, 572, '矢印キー/WASD: えらぶ　Space/Enter: けってい　X/ESC: キャンセル', { fontFamily: FONT, fontSize: '14px', color: '#7986cb' }).setOrigin(0.5);

    // ブラウザは最初の操作まで音を出せないので、何か押したら曲を流す
    const kick = () => playMusic('title');
    this.input.once('pointerdown', kick);
    this.input.keyboard?.once('keydown', kick);
    playMusic('title');
  }

  update(): void {
    if (!this.started) this.ui.update(this.controls);
  }

  private toggleSound(list: SelectList, items: ListItem[]): void {
    setMuted(!isMuted());
    refreshMusic();
    if (!isMuted()) playMusic('title');
    items[2].label = `サウンド: ${isMuted() ? 'OFF' : 'ON'}`;
    list.setItems(items);
  }

  private start(state: ReturnType<typeof newGame>): void {
    this.started = true;
    game.set(state);
    stopMusic();
    this.cameras.main.fadeOut(600);
    this.cameras.main.once('camerafadeoutcomplete', () => this.scene.start('RpgMap', {}));
  }
}
