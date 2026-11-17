import Phaser from 'phaser';
import type { DirectionInput } from '../logic/movement';

/**
 * キーボード・ゲームパッド・タッチ（スマホ）をまとめて扱う入力クラス。
 * - 移動: 矢印キー / WASD / パッドの左スティック・十字キー / 画面左半分ドラッグ（仮想スティック）
 * - 決定(A): Space / Z / Enter / パッド A / 画面右半分タップ
 * - キャンセル(B): X / パッド B
 */
export class GameInput {
  private readonly keys: Record<string, Phaser.Input.Keyboard.Key>;
  private readonly stick = { pointerId: -1, ox: 0, oy: 0, x: 0, y: 0 };
  private touchAction = false;
  private touchPending = false;
  // 押してすぐ離した（1フレーム未満の）入力も取りこぼさないよう、keydown イベントを直接記録する
  private keysPending = new Set<string>();
  private keysPressedNow = new Set<string>();
  private prevDpad = { l: false, r: false, u: false, d: false };
  private touchPressedNow = false;
  private prevPad = { a: false, b: false };
  private padPressed = { a: false, b: false };
  private lastFrame = -1;
  private stickGfx?: Phaser.GameObjects.Graphics;

  constructor(private readonly scene: Phaser.Scene) {
    this.keys = scene.input.keyboard!.addKeys({
      up: 'UP', down: 'DOWN', left: 'LEFT', right: 'RIGHT',
      w: 'W', a: 'A', s: 'S', d: 'D',
      space: 'SPACE', z: 'Z', enter: 'ENTER', x: 'X',
    }) as Record<string, Phaser.Input.Keyboard.Key>;
    scene.input.keyboard!.on('keydown', (e: KeyboardEvent) => {
      if (!e.repeat) this.keysPending.add(e.code);
    });
    // 毎フレーム先頭で「押した瞬間」を確定させる（読まれなかった入力は次のフレームに持ち越さない）
    const onPre = () => this.poll();
    scene.events.on('preupdate', onPre);
    scene.events.once('shutdown', () => scene.events.off('preupdate', onPre));
    if (scene.sys.game.device.input.touch) this.setupTouch();
  }

  private get pad(): Phaser.Input.Gamepad.Gamepad | undefined {
    return this.scene.input.gamepad?.pad1 ?? undefined;
  }

  /** 1フレームに1回だけ「押した瞬間」を計算する */
  private poll(): void {
    const frame = this.scene.game.loop.frame;
    if (frame === this.lastFrame) return;
    this.lastFrame = frame;
    const pad = this.pad;
    const a = !!pad?.A;
    const b = !!pad?.B;
    this.padPressed = { a: a && !this.prevPad.a, b: b && !this.prevPad.b };
    this.prevPad = { a, b };
    this.keysPressedNow = this.keysPending;
    this.keysPending = new Set();
    this.touchPressedNow = this.touchPending;
    this.touchPending = false;
  }

  /** 移動方向（-1〜1）。斜めは長さ 1 以内に収める */
  get axis(): { x: number; y: number } {
    const k = this.keys;
    let x = (k.right.isDown || k.d.isDown ? 1 : 0) - (k.left.isDown || k.a.isDown ? 1 : 0);
    let y = (k.down.isDown || k.s.isDown ? 1 : 0) - (k.up.isDown || k.w.isDown ? 1 : 0);
    const pad = this.pad;
    if (pad) {
      if (Math.abs(pad.leftStick.x) > 0.2) x += pad.leftStick.x;
      if (Math.abs(pad.leftStick.y) > 0.2) y += pad.leftStick.y;
      x += (pad.right ? 1 : 0) - (pad.left ? 1 : 0);
      y += (pad.down ? 1 : 0) - (pad.up ? 1 : 0);
    }
    x += this.stick.x;
    y += this.stick.y;
    const len = Math.hypot(x, y);
    return len > 1 ? { x: x / len, y: y / len } : { x, y };
  }

  /** 上下左右のオン/オフ */
  get dirs(): DirectionInput {
    const { x, y } = this.axis;
    return { left: x < -0.4, right: x > 0.4, up: y < -0.4, down: y > 0.4 };
  }

  /** 決定ボタンを押している間 true */
  get action(): boolean {
    const k = this.keys;
    return k.space.isDown || k.z.isDown || k.enter.isDown || !!this.pad?.A || this.touchAction;
  }

  /** 決定ボタンを押した瞬間だけ true（1フレームに何度呼んでも同じ値） */
  get actionPressed(): boolean {
    this.poll();
    return this.pressed('Space', 'KeyZ', 'Enter') || this.padPressed.a || this.touchPressedNow;
  }

  /** 上キーを押した瞬間（ジャンプを上キーでもできるようにする用） */
  get upPressed(): boolean {
    return this.pressed('ArrowUp', 'KeyW');
  }

  get cancelPressed(): boolean {
    this.poll();
    return this.pressed('KeyX') || this.padPressed.b;
  }

  /** 方向キーを押した瞬間（ターン制のゲーム向け） */
  get dirPressed(): { x: number; y: number } | null {
    if (this.pressed('ArrowLeft', 'KeyA')) return { x: -1, y: 0 };
    if (this.pressed('ArrowRight', 'KeyD')) return { x: 1, y: 0 };
    if (this.pressed('ArrowUp', 'KeyW')) return { x: 0, y: -1 };
    if (this.pressed('ArrowDown', 'KeyS')) return { x: 0, y: 1 };
    const pad = this.pad;
    if (pad) {
      // 十字キーの押した瞬間
      const now = { l: pad.left, r: pad.right, u: pad.up, d: pad.down };
      const prev = this.prevDpad;
      this.prevDpad = now;
      if (now.l && !prev.l) return { x: -1, y: 0 };
      if (now.r && !prev.r) return { x: 1, y: 0 };
      if (now.u && !prev.u) return { x: 0, y: -1 };
      if (now.d && !prev.d) return { x: 0, y: 1 };
    }
    return null;
  }

  /** このフレームで押されたキーか（event.code で指定） */
  private pressed(...codes: string[]): boolean {
    this.poll();
    return codes.some((c) => this.keysPressedNow.has(c));
  }

  private setupTouch(): void {
    const s = this.scene;
    s.input.addPointer(2);
    this.stickGfx = s.add.graphics().setScrollFactor(0).setDepth(10000);
    s.input.on('pointerdown', (p: Phaser.Input.Pointer) => {
      if (p.x < s.scale.width / 2 && this.stick.pointerId === -1) {
        Object.assign(this.stick, { pointerId: p.id, ox: p.x, oy: p.y, x: 0, y: 0 });
      } else if (p.x >= s.scale.width / 2) {
        this.touchAction = true;
        this.touchPending = true;
      }
      this.drawStick();
    });
    s.input.on('pointermove', (p: Phaser.Input.Pointer) => {
      if (p.id !== this.stick.pointerId) return;
      const dx = p.x - this.stick.ox;
      const dy = p.y - this.stick.oy;
      const len = Math.max(50, Math.hypot(dx, dy));
      this.stick.x = dx / len;
      this.stick.y = dy / len;
      this.drawStick();
    });
    s.input.on('pointerup', (p: Phaser.Input.Pointer) => {
      if (p.id === this.stick.pointerId) Object.assign(this.stick, { pointerId: -1, x: 0, y: 0 });
      else this.touchAction = false;
      this.drawStick();
    });
  }

  private drawStick(): void {
    const g = this.stickGfx;
    if (!g) return;
    g.clear();
    if (this.stick.pointerId === -1) return;
    g.fillStyle(0xffffff, 0.15).fillCircle(this.stick.ox, this.stick.oy, 50);
    g.fillStyle(0xffffff, 0.4).fillCircle(this.stick.ox + this.stick.x * 50, this.stick.oy + this.stick.y * 50, 22);
  }
}
