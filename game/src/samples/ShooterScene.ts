import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { createDebugGui } from '../core/debugGui';
import { GameInput } from '../core/input';
import { loadHighScore, saveHighScore } from '../core/save';
import { sfx } from '../core/sfx';
import { addSampleChrome, text } from '../core/ui';

type Img = Phaser.Physics.Arcade.Image;

/** 縦スクロールシューティング。弾は「オブジェクトプール」で使い回して軽くしている。 */
export class ShooterScene extends Phaser.Scene {
  private ship!: Img;
  private controls!: GameInput;
  private bullets!: Phaser.Physics.Arcade.Group;
  private enemyBullets!: Phaser.Physics.Arcade.Group;
  private enemies!: Phaser.Physics.Arcade.Group;
  private explosion!: Phaser.GameObjects.Particles.ParticleEmitter;
  private stars: Phaser.GameObjects.Rectangle[] = [];
  private hud!: Phaser.GameObjects.Text;
  private lastShot = 0;
  private score = 0;
  private lives = 3;
  private invincibleUntil = 0;
  private over = false;
  private params = { shipSpeed: 320, fireIntervalMs: 110, spawnIntervalMs: 700, enemySpeed: 120 };
  private spawnTimer?: Phaser.Time.TimerEvent;

  constructor() {
    super('Shooter');
  }

  create(): void {
    this.score = 0;
    this.lives = 3;
    this.over = false;
    this.cameras.main.setBackgroundColor('#05060f');
    this.stars = Array.from({ length: 80 }, () => {
      const s = Phaser.Math.FloatBetween(1, 3);
      return this.add.rectangle(Phaser.Math.Between(0, GAME_WIDTH), Phaser.Math.Between(0, GAME_HEIGHT), s, s, 0xffffff, s / 3);
    });

    this.ship = this.physics.add.image(GAME_WIDTH / 2, GAME_HEIGHT - 80, 'ship').setCollideWorldBounds(true);
    (this.ship.body as Phaser.Physics.Arcade.Body).setCircle(10, 8, 12); // 当たり判定は見た目より小さく
    this.bullets = this.physics.add.group({ defaultKey: 'bullet', maxSize: 60 });
    this.enemyBullets = this.physics.add.group({ defaultKey: 'ebullet', maxSize: 100 });
    this.enemies = this.physics.add.group({ defaultKey: 'ufo', maxSize: 40 });
    this.explosion = this.add.particles(0, 0, 'particle', {
      speed: { min: 60, max: 280 }, lifespan: 500, scale: { start: 1, end: 0 },
      tint: [0xffd54f, 0xff8a65, 0xffffff], emitting: false,
    });

    this.physics.add.overlap(this.bullets, this.enemies, (b, e) => {
      this.kill(b as Img);
      const enemy = e as Img;
      this.explosion.explode(20, enemy.x, enemy.y);
      this.kill(enemy);
      this.score += 100;
      sfx.explode();
    });
    const hitShip = (_s: unknown, o: unknown) => {
      this.kill(o as Img);
      this.damage();
    };
    this.physics.add.overlap(this.ship, this.enemies, hitShip);
    this.physics.add.overlap(this.ship, this.enemyBullets, hitShip);

    this.startSpawner();
    this.controls = new GameInput(this);
    this.hud = text(this, 16, 16, '', 20).setDepth(10);
    addSampleChrome(this, '移動: 矢印/WASD  ショット: Space 長押し');

    const gui = createDebugGui(this, 'Shooter');
    if (gui) {
      gui.add(this.params, 'shipSpeed', 100, 800);
      gui.add(this.params, 'fireIntervalMs', 30, 500);
      gui.add(this.params, 'spawnIntervalMs', 100, 2000).onChange(() => this.startSpawner());
      gui.add(this.params, 'enemySpeed', 30, 400);
    }
  }

  update(time: number, dt: number): void {
    for (const s of this.stars) {
      s.y += (s.width * 60 * dt) / 1000;
      if (s.y > GAME_HEIGHT) s.setPosition(Phaser.Math.Between(0, GAME_WIDTH), 0);
    }
    this.hud.setText(`SCORE ${this.score}   LIFE ${'♥'.repeat(Math.max(0, this.lives))}   HI ${loadHighScore('shooter')}`);
    if (this.over) {
      if (this.controls.actionPressed) this.scene.restart();
      return;
    }

    const { x, y } = this.controls.axis;
    this.ship.setVelocity(x * this.params.shipSpeed, y * this.params.shipSpeed);
    this.ship.setAlpha(time < this.invincibleUntil ? (Math.floor(time / 80) % 2 ? 0.3 : 1) : 1);

    if (this.controls.action && time - this.lastShot > this.params.fireIntervalMs) {
      this.lastShot = time;
      for (const dx of [-8, 8]) this.fire(this.bullets, this.ship.x + dx, this.ship.y - 16, 0, -700);
      sfx.shoot();
    }

    // 画面外に出たものはプールに戻す
    for (const g of [this.bullets, this.enemyBullets, this.enemies]) {
      for (const c of g.getChildren()) {
        const o = c as Img;
        if (o.active && (o.y < -40 || o.y > GAME_HEIGHT + 40 || o.x < -40 || o.x > GAME_WIDTH + 40)) this.kill(o);
      }
    }
    // 敵: 左右にゆらゆら揺れながら降りてくる
    for (const c of this.enemies.getChildren()) {
      const e = c as Img;
      if (e.active) e.setVelocityX(Math.sin(time / 400 + (e.getData('phase') as number)) * 120);
    }
  }

  private startSpawner(): void {
    this.spawnTimer?.remove();
    this.spawnTimer = this.time.addEvent({ delay: this.params.spawnIntervalMs, loop: true, callback: () => this.spawnEnemy() });
  }

  private fire(group: Phaser.Physics.Arcade.Group, x: number, y: number, vx: number, vy: number): void {
    const b = group.get(x, y) as Img | null;
    if (!b) return;
    b.enableBody(true, x, y, true, true);
    b.setVelocity(vx, vy);
  }

  private kill(o: Img): void {
    o.disableBody(true, true);
  }

  private spawnEnemy(): void {
    if (this.over) return;
    const x = Phaser.Math.Between(40, GAME_WIDTH - 40);
    const e = this.enemies.get(x, -20) as Img | null;
    if (!e) return;
    e.enableBody(true, x, -20, true, true);
    e.setVelocityY(this.params.enemySpeed).setData('phase', Math.random() * 10);
    // 少し後に自機を狙って撃つ
    this.time.delayedCall(Phaser.Math.Between(500, 1500), () => {
      if (!e.active || this.over) return;
      const angle = Phaser.Math.Angle.Between(e.x, e.y, this.ship.x, this.ship.y);
      this.fire(this.enemyBullets, e.x, e.y, Math.cos(angle) * 220, Math.sin(angle) * 220);
    });
  }

  private damage(): void {
    if (this.time.now < this.invincibleUntil || this.over) return;
    this.lives--;
    sfx.hit();
    this.cameras.main.shake(250, 0.015);
    this.invincibleUntil = this.time.now + 1500;
    if (this.lives <= 0) {
      this.over = true;
      this.explosion.explode(60, this.ship.x, this.ship.y);
      this.ship.disableBody(true, true);
      sfx.lose();
      const best = saveHighScore('shooter', this.score);
      text(this, GAME_WIDTH / 2, GAME_HEIGHT / 2, `GAME OVER\nSCORE ${this.score}${best ? '\nNEW RECORD!' : ''}\n\nSPACE でリトライ`, 32)
        .setOrigin(0.5).setAlign('center');
    }
  }
}
