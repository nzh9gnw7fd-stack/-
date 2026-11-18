import Phaser from 'phaser';
import type { GameInput } from '../core/input';
import { sfx } from '../core/sfx';
import { FONT } from '../core/ui';

export const UI_DEPTH = 3000;

export function textStyle(size = 20, color = '#ffffff'): Phaser.Types.GameObjects.Text.TextStyle {
  return { fontFamily: FONT, fontSize: `${size}px`, color };
}

/** RPG らしい青いウィンドウ */
export class Win {
  readonly root: Phaser.GameObjects.Container;
  private readonly bg: Phaser.GameObjects.Graphics;

  constructor(readonly scene: Phaser.Scene, public x: number, public y: number, public w: number, public h: number) {
    this.bg = scene.add.graphics();
    this.root = scene.add.container(x, y, [this.bg]).setScrollFactor(0).setDepth(UI_DEPTH);
    this.draw();
  }

  private draw(): void {
    this.bg.clear();
    this.bg.fillStyle(0x10184a, 0.94).fillRoundedRect(0, 0, this.w, this.h, 8);
    this.bg.lineStyle(3, 0xffffff).strokeRoundedRect(1.5, 1.5, this.w - 3, this.h - 3, 8);
  }

  resize(h: number): void {
    this.h = h;
    this.draw();
  }

  text(x: number, y: number, str: string, size = 20, color = '#ffffff'): Phaser.GameObjects.Text {
    const t = this.scene.add.text(x, y, str, textStyle(size, color));
    this.root.add(t);
    return t;
  }

  /** 中身を消して枠だけにする */
  clear(): void {
    this.root.list.slice(1).forEach((o) => o.destroy());
  }

  destroy(): void {
    this.root.destroy();
  }
}

export interface ListItem {
  label: string;
  /** 右側に出す文字（値段・個数など） */
  right?: string;
  disabled?: boolean;
  onSelect?: () => void;
}

/** カーソルで選ぶリスト。上下で移動、決定で onSelect、キャンセルで onCancel */
export class SelectList {
  readonly win: Win;
  private cursor: Phaser.GameObjects.Image;
  private rows: Phaser.GameObjects.Text[] = [];
  index = 0;
  private scroll = 0;
  onCancel?: () => void;
  onMove?: (index: number) => void;
  /** false のあいだは入力を受け付けない（下のメニューとして残すとき） */
  active = true;

  constructor(
    scene: Phaser.Scene,
    x: number, y: number, w: number,
    private items: ListItem[],
    private readonly opts: { visibleRows?: number; title?: string; rowHeight?: number } = {},
  ) {
    const rows = Math.min(opts.visibleRows ?? 8, Math.max(1, items.length));
    const rh = opts.rowHeight ?? 34;
    const top = opts.title ? 40 : 14;
    this.win = new Win(scene, x, y, w, top + rows * rh + 12);
    if (opts.title) this.win.text(16, 10, opts.title, 18, '#ffd54f');
    this.cursor = scene.add.image(14, 0, 'cursor').setOrigin(0, 0.5);
    this.win.root.add(this.cursor);
    this.render();
  }

  get visible(): number {
    const rh = this.opts.rowHeight ?? 34;
    const top = this.opts.title ? 40 : 14;
    return Math.round((this.win.h - top - 12) / rh);
  }

  setItems(items: ListItem[]): void {
    this.items = items;
    this.index = Math.min(this.index, Math.max(0, items.length - 1));
    this.render();
  }

  get current(): ListItem | undefined {
    return this.items[this.index];
  }

  private render(): void {
    this.rows.forEach((r) => r.destroy());
    this.rows = [];
    const rh = this.opts.rowHeight ?? 34;
    const top = this.opts.title ? 40 : 14;
    const vis = this.visible;
    if (this.index < this.scroll) this.scroll = this.index;
    if (this.index >= this.scroll + vis) this.scroll = this.index - vis + 1;
    this.items.slice(this.scroll, this.scroll + vis).forEach((it, i) => {
      const color = it.disabled ? '#78809a' : '#ffffff';
      const y = top + i * rh;
      const label = this.win.text(36, y, it.label, 20, color);
      label.setInteractive({ useHandCursor: true });
      label.on('pointerdown', (_p: Phaser.Input.Pointer, _x: number, _y: number, e: Phaser.Types.Input.EventData) => {
        e.stopPropagation();
        if (!this.active) return;
        this.index = this.scroll + i;
        this.render();
        this.confirm();
      });
      this.rows.push(label);
      if (it.right) this.rows.push(this.win.text(this.win.w - 20, y, it.right, 20, color).setOrigin(1, 0));
    });
    if (this.items.length === 0) this.rows.push(this.win.text(36, top, '（なし）', 20, '#78809a'));
    this.cursor.setY(top + (this.index - this.scroll) * rh + 13).setVisible(this.items.length > 0);
    if (this.scroll > 0) this.rows.push(this.win.text(this.win.w / 2, top - 14, '▲', 12, '#90caf9').setOrigin(0.5, 0));
    if (this.scroll + vis < this.items.length) this.rows.push(this.win.text(this.win.w / 2, this.win.h - 16, '▼', 12, '#90caf9').setOrigin(0.5, 0));
  }

  move(delta: number): void {
    if (this.items.length === 0) return;
    this.index = Phaser.Math.Wrap(this.index + delta, 0, this.items.length);
    sfx.text();
    this.render();
    this.onMove?.(this.index);
  }

  confirm(): void {
    const it = this.current;
    if (!it) return;
    if (it.disabled) {
      sfx.cancel();
      return;
    }
    sfx.select();
    it.onSelect?.();
  }

  handle(input: GameInput): void {
    if (!this.active) return;
    const d = input.dirPressed;
    if (d?.y) this.move(d.y);
    else if (input.actionPressed) this.confirm();
    else if (input.cancelPressed && this.onCancel) {
      sfx.cancel();
      this.onCancel();
    }
  }

  setActive(v: boolean): this {
    this.active = v;
    this.cursor.setAlpha(v ? 1 : 0.4);
    return this;
  }

  destroy(): void {
    this.win.destroy();
  }
}

/** 重なったメニューを管理する（一番上だけ操作できる） */
export class UIStack {
  private stack: { list?: SelectList; wins: Win[]; onInput?: (input: GameInput) => void }[] = [];

  get open(): boolean {
    return this.stack.length > 0;
  }

  push(list: SelectList | null, extra: Win[] = [], onInput?: (input: GameInput) => void): void {
    this.top?.list?.setActive(false);
    this.stack.push({ list: list ?? undefined, wins: extra, onInput });
  }

  pop(): void {
    const top = this.stack.pop();
    top?.list?.destroy();
    top?.wins.forEach((w) => w.destroy());
    this.top?.list?.setActive(true);
  }

  clear(): void {
    while (this.open) this.pop();
  }

  get top() {
    return this.stack[this.stack.length - 1];
  }

  update(input: GameInput): void {
    const top = this.top;
    if (!top) return;
    if (top.onInput) top.onInput(input);
    else top.list?.handle(input);
  }
}
