import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH, TILE } from '../config';
import { createDebugGui } from '../core/debugGui';
import { GameInput } from '../core/input';
import { sfx } from '../core/sfx';
import { T } from '../core/textures';
import { addSampleChrome, text } from '../core/ui';

/**
 * ステージは文字で描く:  # 地面  B ブロック  ^ トゲ  o コイン  E 敵  P スタート  G ゴール
 * Tiled（無料のマップエディタ）で作ったマップを使う場合は this.load.tilemapTiledJSON() で読み込める。
 */
const LEVEL = [
  '', '', '', '', '', '', '', '', '', '', '',
  '                                  ooo',
  '                                  BBB                                 ooooo',
  '                            ooooo                          o          BBBBB',
  '        ooo                 BBBBB                          B      oo',
  '       BBBBB                                              BB      BBB',
  '   P                    ^^                      E     E  BBB            ^^^  E       G',
  '##############   #######################   ###################   #########################',
  '##############   #######################   ###################   #########################',
];

export class PlatformerScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Sprite;
  private controls!: GameInput;
  private enemies!: Phaser.Physics.Arcade.Group;
  private spawn = { x: 0, y: 0 };
  private coins = 0;
  private hud!: Phaser.GameObjects.Text;
  private lastGrounded = 0;
  private jumpBufferedAt = -Infinity;
  private cleared = false;
  private startTime = 0;
  /** デバッグパネルから調整できるパラメータ */
  private params = { gravity: 1400, runSpeed: 240, accel: 1800, jumpSpeed: 600, coyoteMs: 100, jumpBufferMs: 120 };

  constructor() {
    super('Platformer');
  }

  create(): void {
    this.coins = 0;
    this.cleared = false;
    this.startTime = this.time.now;
    const width = Math.max(...LEVEL.map((r) => r.length));
    const worldW = width * TILE;
    const worldH = LEVEL.length * TILE;

    // 背景（スクロール速度を変えて奥行きを出す = パララックス）
    this.cameras.main.setBackgroundColor('#87ceeb');
    for (let i = 0; i < 12; i++) {
      this.add.circle(i * 260 + 100, 140 + (i % 3) * 30, 40 + (i % 2) * 20, 0xffffff, 0.9).setScrollFactor(0.2);
      this.add.triangle(i * 300, worldH - 64, 0, 200, 160, 0, 320, 200, 0x9ccc65).setOrigin(0, 1).setScrollFactor(0.5);
    }

    // 文字列 → タイルマップ
    const data = LEVEL.map((row) => [...row.padEnd(width)].map((ch) => (ch === '#' ? T.GROUND : ch === 'B' ? T.BRICK : -1)));
    const map = this.make.tilemap({ data, tileWidth: TILE, tileHeight: TILE });
    const layer = map.createLayer(0, map.addTilesetImage('tiles')!, 0, 0)!;
    layer.setCollision([T.GROUND, T.BRICK]);

    const coins = this.physics.add.staticGroup();
    const spikes = this.physics.add.staticGroup();
    this.enemies = this.physics.add.group();
    let goal: Phaser.Types.Physics.Arcade.ImageWithStaticBody | null = null;
    LEVEL.forEach((row, ty) => [...row].forEach((ch, tx) => {
      const x = tx * TILE + TILE / 2;
      const y = ty * TILE + TILE / 2;
      if (ch === 'o') coins.create(x, y, 'coin');
      if (ch === '^') (spikes.create(x, y, 'spike') as Phaser.Physics.Arcade.Image).setSize(28, 16).setOffset(2, 16);
      if (ch === 'P') this.spawn = { x, y };
      if (ch === 'E') (this.enemies.create(x, y, 'enemy') as Phaser.Physics.Arcade.Sprite).setVelocityX(-60).setCollideWorldBounds(true);
      if (ch === 'G') goal = this.physics.add.staticImage(x, y - TILE, 'flag');
    }));

    this.player = this.physics.add.sprite(this.spawn.x, this.spawn.y, 'player').setCollideWorldBounds(true);
    this.player.setSize(26, 30).setMaxVelocity(this.params.runSpeed, 1000);
    this.physics.world.setBounds(0, 0, worldW, worldH + 200);
    this.physics.world.setBoundsCollision(true, true, true, false); // 下は落ちられる
    this.cameras.main.setBounds(0, 0, worldW, worldH).startFollow(this.player, true, 0.15, 0.15);

    this.physics.add.collider(this.player, layer);
    this.physics.add.collider(this.enemies, layer);
    this.physics.add.overlap(this.player, coins, (_p, c) => {
      (c as Phaser.Physics.Arcade.Image).destroy();
      this.coins++;
      sfx.coin();
    });
    this.physics.add.overlap(this.player, spikes, () => this.die());
    this.physics.add.overlap(this.player, this.enemies, (_p, e) => {
      const enemy = e as Phaser.Physics.Arcade.Sprite;
      const body = this.player.body as Phaser.Physics.Arcade.Body;
      if (body.velocity.y > 0 && body.bottom < enemy.y) {
        // 踏みつけ
        enemy.destroy();
        this.player.setVelocityY(-this.params.jumpSpeed * 0.6);
        sfx.hit();
      } else {
        this.die();
      }
    });
    if (goal) this.physics.add.overlap(this.player, goal, () => this.clear());

    this.controls = new GameInput(this);
    this.hud = text(this, 16, 16, '', 22, '#1d2033');
    addSampleChrome(this, '移動: ←→  ジャンプ: Space/↑');

    const gui = createDebugGui(this, 'Platformer');
    if (gui) {
      gui.add(this.params, 'gravity', 300, 3000);
      gui.add(this.params, 'runSpeed', 50, 600).onChange((v: number) => this.player.setMaxVelocity(v, 1000));
      gui.add(this.params, 'accel', 200, 5000);
      gui.add(this.params, 'jumpSpeed', 200, 1200);
      gui.add(this.params, 'coyoteMs', 0, 300);
      gui.add(this.params, 'jumpBufferMs', 0, 300);
      gui.add(this.physics.world, 'drawDebug').name('当たり判定を表示').onChange((v: boolean) => {
        if (v && !this.physics.world.debugGraphic) this.physics.world.createDebugGraphic();
        this.physics.world.debugGraphic?.setVisible(v);
      });
    }
  }

  update(time: number): void {
    this.physics.world.gravity.y = this.params.gravity;
    for (const e of this.enemies.getChildren()) {
      const s = e as Phaser.Physics.Arcade.Sprite;
      const b = s.body as Phaser.Physics.Arcade.Body;
      if (b.blocked.left) s.setVelocityX(60);
      else if (b.blocked.right) s.setVelocityX(-60);
    }
    if (this.cleared) return;

    const body = this.player.body as Phaser.Physics.Arcade.Body;
    const { x } = this.controls.axis;
    body.setAccelerationX(x * this.params.accel);
    body.setDragX(x === 0 ? this.params.accel : 0);
    if (x !== 0) this.player.setFlipX(x < 0);

    // コヨーテタイム（足場を離れた直後でもジャンプ可）とジャンプ先行入力で操作感を良くする
    if (body.blocked.down) this.lastGrounded = time;
    const jumpPressed = this.controls.actionPressed || this.controls.upPressed;
    if (jumpPressed) this.jumpBufferedAt = time;
    if (time - this.jumpBufferedAt < this.params.jumpBufferMs && time - this.lastGrounded < this.params.coyoteMs) {
      body.setVelocityY(-this.params.jumpSpeed);
      this.jumpBufferedAt = -Infinity;
      this.lastGrounded = -Infinity;
      sfx.jump();
    }
    // ボタンを早く離すと低いジャンプ
    if (!this.controls.action && !this.controls.dirs.up && body.velocity.y < -200) body.setVelocityY(-200);

    if (this.player.y > LEVEL.length * TILE + 50) this.die();
    this.hud.setText(`COIN: ${this.coins}   TIME: ${((time - this.startTime) / 1000).toFixed(1)}`);
  }

  private die(): void {
    if (this.cleared) return;
    sfx.lose();
    this.cameras.main.shake(200, 0.01);
    this.player.setPosition(this.spawn.x, this.spawn.y).setVelocity(0, 0);
  }

  private clear(): void {
    if (this.cleared) return;
    this.cleared = true;
    sfx.powerup();
    this.player.setVelocity(0, 0).setAcceleration(0, 0);
    const t = ((this.time.now - this.startTime) / 1000).toFixed(1);
    text(this, GAME_WIDTH / 2, GAME_HEIGHT / 2, `STAGE CLEAR!\nCOIN ${this.coins}  TIME ${t}s\n\nSPACE でもう一度`, 32, '#ffffff')
      .setOrigin(0.5).setAlign('center').setStroke('#1d2033', 6);
    this.time.delayedCall(500, () => this.input.keyboard?.once('keydown-SPACE', () => this.scene.restart()));
  }
}
