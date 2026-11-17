import Phaser from 'phaser';
import { GAME_WIDTH } from '../config';
import { loadHighScore, saveHighScore } from '../core/save';
import { sfx } from '../core/sfx';
import { addSampleChrome, text, tweenAsync } from '../core/ui';
import { collapse, createBoard, findMatches, hasPossibleMove, isAdjacent, swap, type Board, type Cell } from '../logic/match3';

const ROWS = 8;
const COLS = 8;
const KINDS = 6;
const SIZE = 62;
const MOVES = 20;

/** マッチ3パズル。盤面の計算は logic/match3.ts（テスト済み）、ここは見た目と操作だけ。 */
export class Match3Scene extends Phaser.Scene {
  private board!: Board;
  private sprites: (Phaser.GameObjects.Image | null)[][] = [];
  private selected: Cell | null = null;
  private cursor!: Phaser.GameObjects.Rectangle;
  private busy = false;
  private score = 0;
  private moves = MOVES;
  private hud!: Phaser.GameObjects.Text;
  private ox = 0;
  private oy = 60;

  constructor() {
    super('Match3');
  }

  create(): void {
    this.score = 0;
    this.moves = MOVES;
    this.busy = false;
    this.selected = null;
    this.ox = GAME_WIDTH - COLS * SIZE - 40;
    this.add.rectangle(this.ox - 6, this.oy - 6, COLS * SIZE + 12, ROWS * SIZE + 12, 0x0d1020).setOrigin(0);
    // 上から落ちてくる新しいピースを、盤面に入るまで隠すフタ
    this.add.rectangle(this.ox - 6, 0, COLS * SIZE + 12, this.oy - 6, 0x1d2033).setOrigin(0).setDepth(5);

    this.board = createBoard(ROWS, COLS, KINDS);
    this.sprites = this.board.map((row, r) => row.map((k, c) => {
      return this.add.image(this.cx(c), this.cy(r), `gem${k}`);
    }));
    this.cursor = this.add.rectangle(0, 0, SIZE, SIZE).setStrokeStyle(4, 0xffffff).setVisible(false);

    this.hud = text(this, 24, 80, '', 22).setLineSpacing(10);
    text(this, 24, 30, 'MATCH 3', 32, '#ffd54f').setFontStyle('bold');
    addSampleChrome(this, 'クリック or ドラッグで隣と入れ替え');
    this.updateHud();

    let downCell: Cell | null = null;
    let downPos = { x: 0, y: 0 };
    this.input.on('pointerdown', (p: Phaser.Input.Pointer) => {
      const cell = this.cellAt(p.x, p.y);
      if (!cell || this.busy) return;
      downCell = cell;
      downPos = { x: p.x, y: p.y };
      if (this.selected && isAdjacent(this.selected, cell)) {
        void this.trySwap(this.selected, cell);
      } else {
        this.select(cell);
      }
    });
    this.input.on('pointermove', (p: Phaser.Input.Pointer) => {
      if (!p.isDown || !downCell || this.busy) return;
      const dx = p.x - downPos.x;
      const dy = p.y - downPos.y;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < SIZE / 2) return;
      const to = Math.abs(dx) > Math.abs(dy) ? { r: downCell.r, c: downCell.c + Math.sign(dx) } : { r: downCell.r + Math.sign(dy), c: downCell.c };
      const from = downCell;
      downCell = null;
      if (to.r >= 0 && to.r < ROWS && to.c >= 0 && to.c < COLS) void this.trySwap(from, to);
    });
    this.input.on('pointerup', () => (downCell = null));
  }

  private cx(c: number) { return this.ox + c * SIZE + SIZE / 2; }
  private cy(r: number) { return this.oy + r * SIZE + SIZE / 2; }

  private cellAt(x: number, y: number): Cell | null {
    const c = Math.floor((x - this.ox) / SIZE);
    const r = Math.floor((y - this.oy) / SIZE);
    return r >= 0 && r < ROWS && c >= 0 && c < COLS ? { r, c } : null;
  }

  private select(cell: Cell | null): void {
    this.selected = cell;
    this.cursor.setVisible(!!cell);
    if (cell) {
      this.cursor.setPosition(this.cx(cell.c), this.cy(cell.r));
      sfx.select();
    }
  }

  private async trySwap(a: Cell, b: Cell): Promise<void> {
    if (this.moves <= 0) return;
    this.busy = true;
    this.select(null);
    await this.animateSwap(a, b);
    const next = swap(this.board, a, b);
    if (findMatches(next).length === 0) {
      sfx.cancel();
      await this.animateSwap(a, b); // 揃わなければ元に戻す
    } else {
      this.board = next;
      this.moves--;
      await this.resolve();
    }
    this.updateHud();
    if (this.moves <= 0) this.finish();
    this.busy = false;
  }

  private async animateSwap(a: Cell, b: Cell): Promise<void> {
    const sa = this.sprites[a.r][a.c]!;
    const sb = this.sprites[b.r][b.c]!;
    this.sprites[a.r][a.c] = sb;
    this.sprites[b.r][b.c] = sa;
    await Promise.all([
      tweenAsync(this, { targets: sa, x: this.cx(b.c), y: this.cy(b.r), duration: 160 }),
      tweenAsync(this, { targets: sb, x: this.cx(a.c), y: this.cy(a.r), duration: 160 }),
    ]);
  }

  /** 揃ったら消す → 落とす → 補充 を、連鎖が止まるまで繰り返す */
  private async resolve(): Promise<void> {
    for (let chain = 1; ; chain++) {
      const matches = findMatches(this.board);
      if (matches.length === 0) break;
      this.score += matches.length * 10 * chain;
      sfx.coin();
      if (chain > 1) this.popup(`${chain} CHAIN!`);
      await Promise.all(matches.map(({ r, c }) => {
        const s = this.sprites[r][c]!;
        this.sprites[r][c] = null;
        this.board[r][c] = -1;
        return tweenAsync(this, { targets: s, scale: 0, angle: 180, duration: 200 }).then(() => s.destroy());
      }));
      const { board, moves } = collapse(this.board, KINDS);
      const old = this.sprites.map((row) => row.slice());
      const anims: Promise<void>[] = [];
      for (const m of moves) {
        let s: Phaser.GameObjects.Image;
        if (m.from) {
          s = old[m.from.r][m.from.c]!;
        } else {
          s = this.add.image(this.cx(m.to.c), this.cy(-1 - (m.spawnIndex ?? 0)), `gem${m.kind}`);
        }
        this.sprites[m.to.r][m.to.c] = s;
        anims.push(tweenAsync(this, { targets: s, y: this.cy(m.to.r), duration: 250, ease: 'Bounce.Out' }));
      }
      this.board = board;
      this.updateHud();
      await Promise.all(anims);
    }
    if (!hasPossibleMove(this.board)) {
      this.popup('シャッフル');
      this.scene.restart(); // 簡易版: 動かせる手がなくなったら作り直す
    }
  }

  private popup(msg: string): void {
    const t = text(this, this.ox + (COLS * SIZE) / 2, this.oy + (ROWS * SIZE) / 2, msg, 40, '#ffd54f').setOrigin(0.5).setStroke('#000', 6).setDepth(10);
    this.tweens.add({ targets: t, y: t.y - 60, alpha: 0, duration: 800, onComplete: () => t.destroy() });
  }

  private updateHud(): void {
    this.hud.setText(`SCORE\n${this.score}\n\nのこり手数\n${this.moves}\n\nHI ${loadHighScore('match3')}`);
  }

  private finish(): void {
    const best = saveHighScore('match3', this.score);
    sfx.powerup();
    text(this, this.ox + (COLS * SIZE) / 2, this.oy + (ROWS * SIZE) / 2, `おわり！\n${this.score} 点${best ? '\nNEW RECORD!' : ''}\n\nクリックでもう一度`, 34)
      .setOrigin(0.5).setAlign('center').setStroke('#000', 6).setDepth(10);
    this.time.delayedCall(600, () => this.input.once('pointerdown', () => this.scene.restart()));
  }
}
