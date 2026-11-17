import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { sfx } from '../core/sfx';
import { addSampleChrome, text } from '../core/ui';

const LAUNCH = { x: 110, y: 430 };

/** Matter.js（本格的な物理エンジン）のサンプル。回転・摩擦・積み重ねができる。 */
export class PhysicsScene extends Phaser.Scene {
  private aim!: Phaser.GameObjects.Graphics;
  private boxes: Phaser.Physics.Matter.Image[] = [];
  private fallen = new Set<Phaser.Physics.Matter.Image>();
  private shots = 0;
  private hud!: Phaser.GameObjects.Text;

  constructor() {
    // このシーンだけ物理エンジンを Matter に切り替える
    super({ key: 'Physics', physics: { default: 'matter', matter: { gravity: { x: 0, y: 1 }, debug: false } } });
  }

  create(): void {
    this.boxes = [];
    this.fallen.clear();
    this.shots = 0;
    this.cameras.main.setBackgroundColor('#263238');
    this.matter.world.setBounds(0, -400, GAME_WIDTH, GAME_HEIGHT + 400, 64, true, true, false, true);

    const ground = (x: number, y: number, w: number, h: number, color: number) => {
      this.add.rectangle(x, y, w, h, color);
      this.matter.add.rectangle(x, y, w, h, { isStatic: true, friction: 0.8 });
    };
    ground(GAME_WIDTH / 2, GAME_HEIGHT - 20, GAME_WIDTH, 40, 0x37474f);
    ground(560, 440, 260, 20, 0x8d6e63); // 台

    // ピラミッド状にブロックを積む
    for (let row = 0; row < 6; row++) {
      for (let i = 0; i < 6 - row; i++) {
        const box = this.matter.add.image(460 + row * 20 + i * 40, 410 - row * 40, 'box', undefined, { friction: 0.6, density: 0.002 });
        this.boxes.push(box);
      }
    }
    this.add.circle(LAUNCH.x, LAUNCH.y, 6, 0xffd54f);
    this.aim = this.add.graphics();
    this.hud = text(this, 16, 16, '', 20);
    text(this, 16, 46, 'クリックした方向にボールを発射。台からブロックを全部落とそう', 16, '#b0bec5');
    addSampleChrome(this, '発射: クリック  リセット: R');

    this.input.on('pointermove', (p: Phaser.Input.Pointer) => this.drawAim(p));
    this.input.on('pointerdown', (p: Phaser.Input.Pointer) => this.shoot(p));
    this.input.keyboard?.on('keydown-R', () => this.scene.restart());
    this.updateHud();
  }

  update(): void {
    for (const b of this.boxes) {
      if (!this.fallen.has(b) && b.y > 470) {
        this.fallen.add(b);
        sfx.coin();
        this.updateHud();
      }
    }
  }

  private launchVelocity(p: Phaser.Input.Pointer): { vx: number; vy: number } {
    const dx = p.x - LAUNCH.x;
    const dy = p.y - LAUNCH.y;
    const power = Math.min(Math.hypot(dx, dy), 350) / 350 * 22;
    const a = Math.atan2(dy, dx);
    return { vx: Math.cos(a) * power, vy: Math.sin(a) * power };
  }

  /** 発射したときの軌道を点線で予測表示 */
  private drawAim(p: Phaser.Input.Pointer): void {
    const { vx, vy } = this.launchVelocity(p);
    const g = this.aim.clear().fillStyle(0xffffff, 0.5);
    let x = LAUNCH.x;
    let y = LAUNCH.y;
    let vy2 = vy;
    // Matter の重力は 1 ステップあたり gravity.y * scale(0.001) * delta^2 ≈ 0.28px
    for (let i = 0; i < 40; i++) {
      for (let k = 0; k < 2; k++) { x += vx; vy2 += 0.28; y += vy2; }
      g.fillCircle(x, y, 3);
    }
  }

  private shoot(p: Phaser.Input.Pointer): void {
    if (p.y > GAME_HEIGHT - 40) return;
    const { vx, vy } = this.launchVelocity(p);
    const ball = this.matter.add.image(LAUNCH.x, LAUNCH.y, 'ball', undefined, { restitution: 0.4, density: 0.01 });
    ball.setCircle(15).setVelocity(vx, vy);
    this.time.delayedCall(8000, () => ball.destroy());
    this.shots++;
    sfx.jump();
    this.updateHud();
  }

  private updateHud(): void {
    const left = this.boxes.length - this.fallen.size;
    this.hud.setText(left === 0 ? `クリア！ ${this.shots} 発で全部落とした（R でもう一度）` : `のこり ${left} 個   発射 ${this.shots} 回`);
  }
}
