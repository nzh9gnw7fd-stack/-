import Phaser from 'phaser';
import { FOV, Path, RNG } from 'rot-js';
import { GAME_HEIGHT, TILE } from '../config';
import { GameInput } from '../core/input';
import { sfx } from '../core/sfx';
import { T } from '../core/textures';
import { addSampleChrome, text } from '../core/ui';
import { generateDungeon, type Dungeon } from '../logic/dungeon';

const W = 50;
const H = 36;

interface Actor { x: number; y: number; hp: number; maxHp: number; sprite: Phaser.GameObjects.Image; name: string }

/** ターン制ローグライク。rot.js でダンジョン生成・視界計算・経路探索。 */
export class RoguelikeScene extends Phaser.Scene {
  private dungeon!: Dungeon;
  private layer!: Phaser.Tilemaps.TilemapLayer;
  private player!: Actor;
  private monsters: Actor[] = [];
  private seen = new Set<string>();
  private visible = new Set<string>();
  private controls!: GameInput;
  private log: string[] = [];
  private logText!: Phaser.GameObjects.Text;
  private status!: Phaser.GameObjects.Text;
  private floor = 1;
  private dead = false;

  constructor() {
    super('Roguelike');
  }

  init(data: { floor?: number; hp?: number }): void {
    this.floor = data.floor ?? 1;
    this.dead = false;
    this.log = [];
    this.seen.clear();
    this.monsters = [];
    this.registry.set('rogue.hp', data.hp ?? 20);
  }

  create(): void {
    this.cameras.main.setBackgroundColor('#000000');
    this.dungeon = generateDungeon(W, H, Date.now());
    const data: number[][] = this.dungeon.tiles.map((row) => row.map((t) => (t ? T.FLOOR : T.WALL)));
    data[this.dungeon.stairs.y][this.dungeon.stairs.x] = T.STAIRS;
    const tm = this.make.tilemap({ data, tileWidth: TILE, tileHeight: TILE });
    this.layer = tm.createLayer(0, tm.addTilesetImage('tiles')!, 0, 0) as Phaser.Tilemaps.TilemapLayer;

    const { start } = this.dungeon;
    this.player = this.makeActor(start.x, start.y, 'player', 'あなた', 20);
    this.player.hp = this.registry.get('rogue.hp') as number;
    // 階が深いほど敵が増える
    const count = 3 + this.floor * 2;
    for (let i = 0; i < count; i++) {
      const room = this.dungeon.rooms[1 + Math.floor(RNG.getUniform() * (this.dungeon.rooms.length - 1))];
      if (!room) continue;
      const x = room.x + Math.floor(RNG.getUniform() * 3) - 1;
      const y = room.y + Math.floor(RNG.getUniform() * 3) - 1;
      if (this.dungeon.tiles[y][x] && !this.actorAt(x, y)) this.monsters.push(this.makeActor(x, y, 'enemy', 'スライム', 2 + this.floor));
    }

    this.cameras.main.setBounds(0, 0, W * TILE, H * TILE).startFollow(this.player.sprite, true, 0.3, 0.3);
    this.controls = new GameInput(this);
    this.status = text(this, 16, 12, '', 20).setDepth(10);
    this.logText = text(this, 16, GAME_HEIGHT - 120, '', 16, '#cfd8dc').setDepth(10).setLineSpacing(4);
    addSampleChrome(this, '移動/攻撃: 矢印/WASD  階段: 黄色い床');
    this.message(`地下 ${this.floor} 階にやってきた。`);
    this.computeFov();
  }

  update(): void {
    if (this.dead) {
      if (this.controls.actionPressed) this.scene.restart({});
      return;
    }
    const d = this.controls.dirPressed;
    if (d) this.playerTurn(d.x, d.y);
  }

  private makeActor(x: number, y: number, key: string, name: string, hp: number): Actor {
    const sprite = this.add.image((x + 0.5) * TILE, (y + 0.5) * TILE, key).setDepth(1);
    return { x, y, hp, maxHp: hp, sprite, name };
  }

  private actorAt(x: number, y: number): Actor | undefined {
    return this.monsters.find((m) => m.x === x && m.y === y);
  }

  private passable(x: number, y: number): boolean {
    return this.dungeon.tiles[y]?.[x] === 1;
  }

  private playerTurn(dx: number, dy: number): void {
    const x = this.player.x + dx;
    const y = this.player.y + dy;
    const target = this.actorAt(x, y);
    if (target) {
      this.attack(this.player, target);
    } else if (this.passable(x, y)) {
      this.moveActor(this.player, x, y);
      if (x === this.dungeon.stairs.x && y === this.dungeon.stairs.y) {
        sfx.powerup();
        this.scene.restart({ floor: this.floor + 1, hp: Math.min(20, this.player.hp + 5) });
        return;
      }
    } else {
      return; // 壁: ターンを消費しない
    }
    this.monstersTurn();
    this.computeFov();
  }

  private monstersTurn(): void {
    for (const m of this.monsters) {
      if (!this.visible.has(`${m.x},${m.y}`)) continue; // 見えている（＝相手からも見える）敵だけ動く
      if (Math.abs(m.x - this.player.x) + Math.abs(m.y - this.player.y) === 1) {
        this.attack(m, this.player);
        if (this.dead) return;
        continue;
      }
      const astar = new Path.AStar(this.player.x, this.player.y, (x, y) => this.passable(x, y), { topology: 4 });
      const path: [number, number][] = [];
      astar.compute(m.x, m.y, (x, y) => path.push([x, y]));
      const step = path[1];
      if (step && !this.actorAt(step[0], step[1]) && !(step[0] === this.player.x && step[1] === this.player.y)) {
        this.moveActor(m, step[0], step[1]);
      }
    }
  }

  private attack(a: Actor, b: Actor): void {
    const dmg = 1 + Math.floor(RNG.getUniform() * 3);
    b.hp -= dmg;
    sfx.hit();
    this.tweens.add({ targets: a.sprite, x: a.sprite.x + (b.x - a.x) * 8, y: a.sprite.y + (b.y - a.y) * 8, yoyo: true, duration: 60 });
    this.floatText(b.sprite.x, b.sprite.y, `-${dmg}`, b === this.player ? '#ff5252' : '#ffffff');
    this.message(`${a.name}の攻撃！ ${b.name}に ${dmg} ダメージ。`);
    if (b.hp > 0) return;
    if (b === this.player) {
      this.dead = true;
      sfx.lose();
      this.message(`あなたは倒れた…（地下 ${this.floor} 階）  Space でやり直す`);
      this.cameras.main.fade(1500, 80, 0, 0);
      this.time.delayedCall(1500, () => this.cameras.main.fadeIn(300));
    } else {
      this.message(`${b.name}をたおした！`);
      b.sprite.destroy();
      this.monsters = this.monsters.filter((m) => m !== b);
    }
    this.updateStatus();
  }

  private moveActor(a: Actor, x: number, y: number): void {
    a.x = x;
    a.y = y;
    this.tweens.add({ targets: a.sprite, x: (x + 0.5) * TILE, y: (y + 0.5) * TILE, duration: 80 });
  }

  /** 視界を計算して、見えていない場所を暗くする */
  private computeFov(): void {
    this.visible.clear();
    const fov = new FOV.PreciseShadowcasting((x, y) => this.passable(x, y));
    fov.compute(this.player.x, this.player.y, 8, (x, y) => {
      this.visible.add(`${x},${y}`);
      this.seen.add(`${x},${y}`);
    });
    this.layer.forEachTile((t) => {
      const k = `${t.x},${t.y}`;
      t.setAlpha(this.visible.has(k) ? 1 : this.seen.has(k) ? 0.3 : 0);
    });
    for (const m of this.monsters) m.sprite.setVisible(this.visible.has(`${m.x},${m.y}`));
    this.updateStatus();
  }

  private updateStatus(): void {
    this.status.setText(`地下 ${this.floor} 階   HP ${Math.max(0, this.player.hp)}/${this.player.maxHp}   敵 ${this.monsters.length}`);
  }

  private message(msg: string): void {
    this.log.push(msg);
    this.log = this.log.slice(-4);
    this.logText?.setText(this.log.join('\n'));
  }

  private floatText(x: number, y: number, str: string, color: string): void {
    const t = this.add.text(x, y - 10, str, { fontSize: '18px', color, fontStyle: 'bold' }).setOrigin(0.5).setDepth(5);
    this.tweens.add({ targets: t, y: y - 40, alpha: 0, duration: 700, onComplete: () => t.destroy() });
  }
}

