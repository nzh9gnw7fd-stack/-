import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { DialogueRunner, type Script } from '../logic/dialogue';
import { sfx } from './sfx';
import { FONT } from './ui';

/**
 * 画面下のメッセージウィンドウ。文字送り（タイプライター）と選択肢に対応。
 * DialogueRunner と組み合わせて、RPG の会話やノベルゲームに使う。
 */
export class DialogueBox {
  private readonly root: Phaser.GameObjects.Container;
  private readonly nameText: Phaser.GameObjects.Text;
  private readonly body: Phaser.GameObjects.Text;
  private readonly arrow: Phaser.GameObjects.Text;
  private choiceObjs: Phaser.GameObjects.Text[] = [];
  private choiceIndex = 0;
  private full = '';
  private shown = 0;
  private timer?: Phaser.Time.TimerEvent;
  private runner: DialogueRunner | null = null;
  private onEnd?: () => void;
  /** ノードが表示されるたびに呼ばれる（背景を変える等） */
  onNode?: (runner: DialogueRunner) => void;

  constructor(private readonly scene: Phaser.Scene) {
    const h = 150;
    const y = GAME_HEIGHT - h - 40;
    const bg = scene.add.rectangle(0, 0, GAME_WIDTH - 40, h, 0x0d1020, 0.88).setOrigin(0).setStrokeStyle(2, 0x90caf9);
    this.nameText = scene.add.text(16, -14, '', { fontFamily: FONT, fontSize: '18px', color: '#ffd54f', backgroundColor: '#0d1020', padding: { x: 8, y: 2 } });
    this.body = scene.add.text(20, 22, '', { fontFamily: FONT, fontSize: '20px', color: '#ffffff', wordWrap: { width: GAME_WIDTH - 90, useAdvancedWrap: true }, lineSpacing: 6 });
    this.arrow = scene.add.text(GAME_WIDTH - 70, h - 30, '▼', { fontFamily: FONT, fontSize: '16px', color: '#90caf9' });
    scene.tweens.add({ targets: this.arrow, alpha: 0.2, yoyo: true, repeat: -1, duration: 400 });
    this.root = scene.add.container(20, y, [bg, this.nameText, this.body, this.arrow]).setScrollFactor(0).setDepth(2000).setVisible(false);
  }

  get isOpen(): boolean {
    return this.runner !== null;
  }

  /** 会話を開始する。終わったら onEnd が呼ばれる */
  start(script: Script, opts: { start?: string; flags?: Record<string, boolean | number | string>; onEnd?: () => void } = {}): DialogueRunner {
    this.runner = new DialogueRunner(script, opts.start, opts.flags);
    this.onEnd = opts.onEnd;
    this.root.setVisible(true);
    this.render();
    return this.runner;
  }

  /** 決定ボタン: 文字送り中なら全文表示、選択肢なら決定、それ以外は次へ */
  confirm(): void {
    const r = this.runner;
    if (!r) return;
    if (this.shown < this.full.length) {
      this.shown = this.full.length;
      this.body.setText(this.full);
      this.finishTyping();
      return;
    }
    if (r.choices.length > 0) {
      sfx.select();
      r.choose(this.choiceIndex);
    } else {
      r.advance();
    }
    this.render();
  }

  /** 上下キーで選択肢を移動 */
  moveChoice(delta: number): void {
    if (this.choiceObjs.length === 0) return;
    this.choiceIndex = Phaser.Math.Wrap(this.choiceIndex + delta, 0, this.choiceObjs.length);
    sfx.text();
    this.highlightChoice();
  }

  private render(): void {
    const r = this.runner!;
    this.clearChoices();
    const node = r.node;
    if (!node) {
      this.close();
      return;
    }
    this.onNode?.(r);
    this.nameText.setText(node.speaker ?? '').setVisible(!!node.speaker);
    this.full = node.text;
    this.shown = 0;
    this.body.setText('');
    this.arrow.setVisible(false);
    this.timer?.remove();
    this.timer = this.scene.time.addEvent({
      delay: 30,
      loop: true,
      callback: () => {
        this.shown++;
        this.body.setText(this.full.slice(0, this.shown));
        if (this.shown % 2 === 0) sfx.text();
        if (this.shown >= this.full.length) this.finishTyping();
      },
    });
  }

  private finishTyping(): void {
    this.timer?.remove();
    const choices = this.runner?.choices ?? [];
    this.arrow.setVisible(choices.length === 0);
    this.choiceIndex = 0;
    const baseY = this.root.y - 16 - choices.length * 44;
    this.choiceObjs = choices.map((c, i) => {
      const t = this.scene.add
        .text(GAME_WIDTH / 2, baseY + i * 44, c.text, { fontFamily: FONT, fontSize: '20px', color: '#ffffff', backgroundColor: '#2b3050', padding: { x: 24, y: 8 }, fixedWidth: 420, align: 'center' })
        .setOrigin(0.5, 0).setScrollFactor(0).setDepth(2001).setInteractive({ useHandCursor: true });
      t.on('pointerover', () => { this.choiceIndex = i; this.highlightChoice(); });
      t.on('pointerdown', (_p: Phaser.Input.Pointer, _x: number, _y: number, e: Phaser.Types.Input.EventData) => {
        e.stopPropagation();
        this.choiceIndex = i;
        this.confirm();
      });
      return t;
    });
    this.highlightChoice();
  }

  private highlightChoice(): void {
    this.choiceObjs.forEach((t, i) => t.setBackgroundColor(i === this.choiceIndex ? '#4f5aa0' : '#2b3050'));
  }

  private clearChoices(): void {
    this.choiceObjs.forEach((t) => t.destroy());
    this.choiceObjs = [];
  }

  close(): void {
    this.timer?.remove();
    this.clearChoices();
    this.root.setVisible(false);
    this.runner = null;
    const cb = this.onEnd;
    this.onEnd = undefined;
    cb?.();
  }
}
