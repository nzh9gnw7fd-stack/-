import Phaser from 'phaser';
import { Path } from 'rot-js';
import { GAME_HEIGHT, GAME_WIDTH, TILE } from '../config';
import { DialogueBox } from '../core/dialogueBox';
import { GameInput } from '../core/input';
import { mulberry32 } from '../core/random';
import { T } from '../core/textures';
import { addSampleChrome, text } from '../core/ui';
import type { Script } from '../logic/dialogue';
import { findStart, generateTerrain, isWalkable } from '../logic/terrain';

const SIZE = 120;
const SPEED = 180;

const VILLAGER_TALK: Script[] = [
  {
    start: { speaker: '村人A', text: 'ようこそ！ このマップは「ノイズ」という仕組みで自動生成されているんだ。', next: 'b' },
    b: { speaker: '村人A', text: 'シード値を変えると、まったく違う島になるよ。', next: undefined },
  },
  {
    start: { speaker: '村人B', text: '地面をクリックすると、そこまで自動で歩いていくよ。', next: 'b' },
    b: { speaker: '村人B', text: '水と山は通れないから、ちゃんと回り道してくれるんだ。（A* 経路探索）' },
  },
  {
    start: {
      speaker: '旅の商人', text: '薬草はいかが？',
      choices: [
        { text: '買う', next: 'buy', if: '!bought', set: { bought: true } },
        { text: 'もう持っている', next: 'have', if: 'bought' },
        { text: 'いらない', next: 'no' },
      ],
    },
    buy: { speaker: '旅の商人', text: 'まいど！ （フラグ bought が立った。もう一度話しかけてみよう）' },
    have: { speaker: '旅の商人', text: 'おや、さっきの薬草ですね。お大事に。' },
    no: { speaker: '旅の商人', text: 'またどうぞ。' },
  },
];

/** RPG のフィールド。地形の自動生成・クリック移動（経路探索）・NPC との会話・ミニマップ。 */
export class FieldScene extends Phaser.Scene {
  private map!: number[][];
  private player!: Phaser.Physics.Arcade.Sprite;
  private controls!: GameInput;
  private npcs: Phaser.Physics.Arcade.Image[] = [];
  private dialogue!: DialogueBox;
  private path: { x: number; y: number }[] = [];
  private hint!: Phaser.GameObjects.Text;
  private flags: Record<string, boolean> = {};
  private seed = 1;

  constructor() {
    super('Field');
  }

  init(data: { seed?: number }): void {
    this.seed = data.seed ?? Math.floor(Math.random() * 100000);
  }

  create(): void {
    this.map = generateTerrain(SIZE, SIZE, this.seed);
    const tm = this.make.tilemap({ data: this.map, tileWidth: TILE, tileHeight: TILE });
    const layer = tm.createLayer(0, tm.addTilesetImage('tiles')!, 0, 0)!;
    layer.setCollision([T.WATER, T.MOUNTAIN]);

    const start = findStart(this.map);
    this.player = this.physics.add.sprite((start.x + 0.5) * TILE, (start.y + 0.5) * TILE, 'player').setSize(24, 24).setDepth(2);
    this.physics.add.collider(this.player, layer);
    const worldW = SIZE * TILE;
    this.physics.world.setBounds(0, 0, worldW, worldW);
    this.player.setCollideWorldBounds(true);
    this.cameras.main.setBounds(0, 0, worldW, worldW).startFollow(this.player, true, 0.2, 0.2);

    // スタート付近の草地に NPC を配置
    const rng = mulberry32(this.seed);
    this.npcs = VILLAGER_TALK.map((_, i) => {
      let p = start;
      for (let tries = 0; tries < 200; tries++) {
        const x = start.x + Math.floor(rng() * 14) - 7;
        const y = start.y + Math.floor(rng() * 14) - 7;
        if (this.map[y]?.[x] === T.GRASS && (x !== start.x || y !== start.y)) { p = { x, y }; break; }
      }
      const npc = this.physics.add.staticImage((p.x + 0.5) * TILE, (p.y + 0.5) * TILE, 'npc').setDepth(1);
      npc.setData('talk', i);
      return npc;
    });
    this.physics.add.collider(this.player, this.npcs);

    // ミニマップ = 縮小したカメラをもう1台置く
    const mini = this.cameras.add(GAME_WIDTH - 170, 10, 160, 160).setZoom(160 / worldW).setBackgroundColor(0x000000);
    mini.centerOn(worldW / 2, worldW / 2);
    const marker = this.add.circle(0, 0, 80, 0xff1744).setDepth(5);
    this.cameras.main.ignore(marker);
    this.events.on('update', () => marker.setPosition(this.player.x, this.player.y));

    this.dialogue = new DialogueBox(this);
    this.controls = new GameInput(this);
    const hud = [
      text(this, 16, 16, `シード: ${this.seed}（R で再生成）`, 16),
      (this.hint = text(this, GAME_WIDTH / 2, GAME_HEIGHT - 70, '', 18, '#ffd54f').setOrigin(0.5)),
    ];
    addSampleChrome(this, '移動: 矢印/WASD・クリック  話す: Space');
    // HUD やウィンドウはミニマップに映さない
    mini.ignore([...hud, ...this.children.list.filter((o) => (o as unknown as { scrollFactorX: number }).scrollFactorX === 0)]);

    this.input.on('pointerdown', (p: Phaser.Input.Pointer) => {
      if (this.dialogue.isOpen) return this.dialogue.confirm();
      this.walkTo(Math.floor(p.worldX / TILE), Math.floor(p.worldY / TILE));
    });
    this.input.keyboard?.on('keydown-R', () => !this.dialogue.isOpen && this.scene.restart({ seed: undefined }));
  }

  update(): void {
    const body = this.player.body as Phaser.Physics.Arcade.Body;
    if (this.dialogue.isOpen) {
      body.setVelocity(0, 0);
      this.hint.setText('');
      if (this.controls.actionPressed) this.dialogue.confirm();
      const d = this.controls.dirPressed;
      if (d?.y) this.dialogue.moveChoice(d.y);
      return;
    }

    let { x, y } = this.controls.axis;
    if (x !== 0 || y !== 0) {
      this.path = [];
    } else if (this.path.length > 0) {
      // 経路に沿って歩く
      const next = this.path[0];
      const tx = (next.x + 0.5) * TILE;
      const ty = (next.y + 0.5) * TILE;
      const dist = Phaser.Math.Distance.Between(this.player.x, this.player.y, tx, ty);
      if (dist < 4) this.path.shift();
      else { x = (tx - this.player.x) / dist; y = (ty - this.player.y) / dist; }
    }
    body.setVelocity(x * SPEED, y * SPEED);

    const near = this.npcs.find((n) => Phaser.Math.Distance.Between(n.x, n.y, this.player.x, this.player.y) < TILE * 1.6);
    this.hint.setText(near ? 'Space で話す' : '');
    if (near && this.controls.actionPressed) {
      this.path = [];
      this.dialogue.start(VILLAGER_TALK[near.getData('talk') as number], { flags: this.flags });
    }
  }

  /** rot.js の A* で経路を求める */
  private walkTo(tx: number, ty: number): void {
    if (!isWalkable(this.map[ty]?.[tx] ?? T.WATER)) return;
    const sx = Math.floor(this.player.x / TILE);
    const sy = Math.floor(this.player.y / TILE);
    const astar = new Path.AStar(tx, ty, (x, y) => isWalkable(this.map[y]?.[x] ?? T.WATER), { topology: 4 });
    const path: { x: number; y: number }[] = [];
    astar.compute(sx, sy, (x, y) => path.push({ x, y }));
    this.path = path.slice(1);
  }
}
