import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { DialogueBox } from '../core/dialogueBox';
import { GameInput } from '../core/input';
import { addSampleChrome, text } from '../core/ui';
import { NOVEL_SCRIPT } from '../data/novelScript';

/**
 * ノベル / アドベンチャー。シナリオは data/novelScript.ts に分けてある。
 * 立ち絵や背景画像を使う場合は、portrait / bg にキー名を書き、this.add.image() で表示すればよい。
 */
export class NovelScene extends Phaser.Scene {
  private dialogue!: DialogueBox;
  private controls!: GameInput;
  private portrait!: Phaser.GameObjects.Container;
  private ended = false;

  constructor() {
    super('Novel');
  }

  create(): void {
    this.ended = false;
    this.controls = new GameInput(this);
    // 立ち絵（仮）: 図形で作った人物シルエット
    const head = this.add.circle(0, -150, 60, 0xffffff);
    const bodyShape = this.add.ellipse(0, 20, 200, 260, 0xffffff);
    this.portrait = this.add.container(GAME_WIDTH / 2, GAME_HEIGHT / 2 + 40, [bodyShape, head]).setAlpha(0);

    this.dialogue = new DialogueBox(this);
    this.dialogue.onNode = (runner) => {
      const node = runner.node!;
      if (node.bg) this.cameras.main.setBackgroundColor(node.bg);
      if (node.portrait) {
        const color = Phaser.Display.Color.HexStringToColor(node.portrait).color;
        head.setFillStyle(color);
        bodyShape.setFillStyle(color);
        this.tweens.add({ targets: this.portrait, alpha: 1, duration: 300 });
      } else {
        this.tweens.add({ targets: this.portrait, alpha: 0, duration: 300 });
      }
    };
    this.dialogue.start(NOVEL_SCRIPT, {
      onEnd: () => {
        this.ended = true;
        text(this, GAME_WIDTH / 2, GAME_HEIGHT / 2, 'クリック / Space で最初から', 22, '#90a4ae').setOrigin(0.5);
      },
    });
    addSampleChrome(this, '進む: クリック/Space  選択: ↑↓');
    this.input.on('pointerdown', () => (this.ended ? this.scene.restart() : this.dialogue.confirm()));
  }

  update(): void {
    if (this.controls.actionPressed) {
      if (this.ended) this.scene.restart();
      else this.dialogue.confirm();
    }
    const d = this.controls.dirPressed;
    if (d?.y) this.dialogue.moveChoice(d.y);
  }
}
