import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../../config';
import { DialogueBox } from '../../core/dialogueBox';
import { GameInput } from '../../core/input';
import { sfx } from '../../core/sfx';
import { FONT } from '../../core/ui';
import type { Script } from '../../logic/dialogue';
import { rollEncounter } from '../battle';
import { ENCOUNTERS, EQUIPS, ITEMS, type EnemyId } from '../data';
import { EVENTS, type EventContext } from '../events';
import { openFieldMenu, openShop } from '../fieldMenu';
import { MAPS, isSolid, tileAt, type ChestDef, type MapDef, type NpcDef } from '../maps';
import { playMusic } from '../music';
import { addEquip, addItem, game, healAll, type Dir } from '../state';
import { RT } from '../textures';
import { UIStack } from '../ui';

const DIRV: Record<Dir, [number, number]> = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
const STEP_MS = 170;

interface Npc { def: NpcDef; sprite: Phaser.GameObjects.Image; x: number; y: number; moving: boolean }
interface Chest { def: ChestDef; sprite: Phaser.GameObjects.Image }

export interface MapSceneData {
  afterBattle?: 'win' | 'fled' | 'lose';
  onWin?: () => void;
}

/** フィールド・村・洞窟を歩き回るシーン（どのマップもこの1つで表示する） */
export class MapScene extends Phaser.Scene {
  private map!: MapDef;
  private hero!: Phaser.GameObjects.Image;
  private npcs: Npc[] = [];
  private chests: Chest[] = [];
  private controls!: GameInput;
  private dialogue!: DialogueBox;
  private ui!: UIStack;
  private moving = false;
  private locked = false;
  private stepsSinceBattle = 0;
  private sceneData: MapSceneData = {};
  private menuBtn!: Phaser.GameObjects.Text;

  constructor() {
    super('RpgMap');
  }

  init(data: MapSceneData): void {
    this.sceneData = data ?? {};
    this.moving = false;
    this.locked = false;
    this.stepsSinceBattle = 0;
  }

  create(): void {
    const s = game.state;
    this.map = MAPS[s.map];
    const map = this.map;
    const w = map.rows[0].length;
    const h = map.rows.length;

    const data = map.rows.map((row) => [...row].map(tileAtChar));
    const tm = this.make.tilemap({ data, tileWidth: RT, tileHeight: RT });
    tm.createLayer(0, tm.addTilesetImage('rpg-tiles')!, 0, 0);

    // マップが画面より小さいときは中央に表示する
    const bw = Math.max(w * RT, GAME_WIDTH);
    const bh = Math.max(h * RT, GAME_HEIGHT);
    this.cameras.main.setBackgroundColor(map.music === 'cave' ? '#100c14' : '#1d3a1a');
    this.cameras.main.setBounds((w * RT - bw) / 2, (h * RT - bh) / 2, bw, bh).setRoundPixels(true);

    this.chests = map.chests.map((def) => ({
      def,
      sprite: this.add.image((def.x + 0.5) * RT, (def.y + 0.5) * RT, s.flags[`chest:${def.id}`] ? 'chest-open' : 'chest').setDepth(def.y),
    }));
    this.npcs = map.npcs.filter((n) => !(n.hideIf && s.flags[n.hideIf])).map((def) => {
      const isPerson = this.textures.exists(`${def.sprite}-down`);
      const sprite = this.add.image((def.x + 0.5) * RT, (def.y + 0.5) * RT, isPerson ? `${def.sprite}-${def.dir === 'left' || def.dir === 'right' ? 'side' : def.dir ?? 'down'}` : def.sprite)
        .setDepth(def.y + 0.5).setScale(def.scale ?? 1);
      if (def.dir === 'left') sprite.setFlipX(true);
      if (!isPerson) sprite.setOrigin(0.5, 0.75);
      return { def, sprite, x: def.x, y: def.y, moving: false };
    });

    this.hero = this.add.image((s.x + 0.5) * RT, (s.y + 0.5) * RT, 'hero-down').setDepth(s.y + 0.6);
    this.face(s.dir);
    this.cameras.main.startFollow(this.hero, true);

    this.controls = new GameInput(this);
    this.dialogue = new DialogueBox(this);
    this.ui = new UIStack();
    playMusic(map.music);

    // タッチ / マウス用のメニューボタン
    const menuBtn = this.menuBtn = this.add.text(GAME_WIDTH - 12, 12, '☰ MENU', { fontFamily: FONT, fontSize: '18px', color: '#ffffff', backgroundColor: '#10184acc', padding: { x: 10, y: 6 } })
      .setOrigin(1, 0).setScrollFactor(0).setDepth(2500).setInteractive({ useHandCursor: true });
    menuBtn.on('pointerdown', (_p: Phaser.Input.Pointer, _x: number, _y: number, e: Phaser.Types.Input.EventData) => {
      e.stopPropagation();
      if (!this.busy) this.openMenu();
    });
    this.input.on('pointerdown', () => {
      if (this.dialogue.isOpen) this.dialogue.confirm();
    });

    // 歩き回る村人
    this.time.addEvent({ delay: 1400, loop: true, callback: () => this.wander() });

    this.cameras.main.fadeIn(250);
    this.showMapName();
    this.afterCreate();
  }

  private afterCreate(): void {
    const s = game.state;
    const d = this.sceneData;
    if (d.afterBattle === 'win' && d.onWin) {
      this.time.delayedCall(300, d.onWin);
    } else if (d.afterBattle === 'lose') {
      this.ctx.talk(undefined, ['……目を覚ますと、村の宿屋のベッドの上だった。', '持っていたお金が半分になっている……。']);
    } else if (!s.flags.prologue) {
      s.flags.prologue = true;
      this.ctx.talk(undefined, [
        'ここはハルナ村。のどかな村の自慢は、決して枯れることのない泉だった。',
        'ところがある朝、その泉がとつぜん干上がってしまった……。',
        '剣士アレン、魔法使いミア、僧侶セラの3人は、村長に呼ばれて村へやってきた。',
        '（操作: 矢印キー/WASD で移動、Space で話す・調べる、X/ESC でメニュー）',
      ]);
    }
  }

  private get busy(): boolean {
    return this.dialogue.isOpen || this.ui.open || this.locked || this.moving;
  }

  update(_t: number, dt: number): void {
    game.state.playMs += dt;
    this.menuBtn.setVisible(!this.ui.open && !this.dialogue.isOpen);
    const c = this.controls;
    if (this.dialogue.isOpen) {
      if (c.actionPressed) this.dialogue.confirm();
      const d = c.dirPressed;
      if (d?.y) this.dialogue.moveChoice(d.y);
      return;
    }
    if (this.ui.open) {
      this.ui.update(c);
      return;
    }
    if (this.locked || this.moving) return;
    if (c.cancelPressed) {
      this.openMenu();
      return;
    }
    if (c.actionPressed) {
      this.interact();
      return;
    }
    // 押しっぱなし（dirs）に加えて、一瞬だけ押した入力（dirPressed）も拾う
    const d = c.dirs;
    const p = c.dirPressed;
    const dir: Dir | null = d.up ? 'up' : d.down ? 'down' : d.left ? 'left' : d.right ? 'right'
      : p ? (p.y < 0 ? 'up' : p.y > 0 ? 'down' : p.x < 0 ? 'left' : 'right') : null;
    if (dir) this.step(dir);
  }

  private face(dir: Dir): void {
    game.state.dir = dir;
    this.hero.setTexture(`hero-${dir === 'left' || dir === 'right' ? 'side' : dir}`).setFlipX(dir === 'left');
  }

  private blocked(x: number, y: number): boolean {
    if (isSolid(this.map, x, y)) return true;
    if (this.npcs.some((n) => n.x === x && n.y === y)) return true;
    if (this.chests.some((c) => c.def.x === x && c.def.y === y)) return true;
    return false;
  }

  private step(dir: Dir): void {
    const s = game.state;
    this.face(dir);
    const [dx, dy] = DIRV[dir];
    const nx = s.x + dx;
    const ny = s.y + dy;
    if (this.blocked(nx, ny)) return;
    this.moving = true;
    s.x = nx;
    s.y = ny;
    this.hero.setDepth(ny + 0.6);
    this.tweens.add({
      targets: this.hero, x: (nx + 0.5) * RT, y: (ny + 0.5) * RT, duration: STEP_MS,
      onComplete: () => {
        this.moving = false;
        this.onStep();
      },
    });
    // てくてく歩いているように少し跳ねる
    this.tweens.add({ targets: this.hero, scaleY: 0.92, duration: STEP_MS / 2, yoyo: true });
  }

  private onStep(): void {
    const s = game.state;
    s.steps++;
    this.stepsSinceBattle++;
    const exit = this.map.exits.find((e) => e.x === s.x && e.y === s.y);
    if (exit) {
      this.changeMap(exit.to, exit.tx, exit.ty, exit.dir);
      return;
    }
    const trig = this.map.triggers.find((t) => t.x === s.x && t.y === s.y);
    if (trig) EVENTS[trig.event]?.(this.ctx);
    if (this.dialogue.isOpen) return;
    // ランダムエンカウント
    const weight = tileAt(this.map, s.x, s.y)?.encounter ?? 0;
    if (this.map.encounter && weight > 0 && this.stepsSinceBattle > 4 && Math.random() < (this.map.rate ?? 0) * weight) {
      this.startBattle(rollEncounter(ENCOUNTERS[this.map.encounter]), {});
    }
  }

  private interact(): void {
    const s = game.state;
    const [dx, dy] = DIRV[s.dir];
    let tx = s.x + dx;
    let ty = s.y + dy;
    // カウンター越しに話せる
    if (this.map.rows[ty]?.[tx] === 'c') { tx += dx; ty += dy; }
    const npc = this.npcs.find((n) => n.x === tx && n.y === ty);
    if (npc) {
      // こちらを向かせる
      const back: Dir = s.dir === 'up' ? 'down' : s.dir === 'down' ? 'up' : s.dir === 'left' ? 'right' : 'left';
      if (this.textures.exists(`${npc.def.sprite}-down`)) {
        npc.sprite.setTexture(`${npc.def.sprite}-${back === 'left' || back === 'right' ? 'side' : back}`).setFlipX(back === 'left');
      }
      EVENTS[npc.def.talk]?.(this.ctx);
      return;
    }
    const chest = this.chests.find((c) => c.def.x === s.x + dx && c.def.y === s.y + dy);
    if (chest) this.openChest(chest);
  }

  private openChest(chest: Chest): void {
    const s = game.state;
    const key = `chest:${chest.def.id}`;
    if (s.flags[key]) {
      this.ctx.talk(undefined, ['宝箱はからっぽだ。']);
      return;
    }
    s.flags[key] = true;
    chest.sprite.setTexture('chest-open');
    sfx.powerup();
    const d = chest.def;
    let name = '';
    if (d.gold) { s.gold += d.gold; name = `${d.gold} ゴールド`; }
    if (d.item) { addItem(s, d.item, d.count ?? 1); name = `${ITEMS[d.item].name}${(d.count ?? 1) > 1 ? ` ×${d.count}` : ''}`; }
    if (d.equip) { addEquip(s, d.equip); name = EQUIPS[d.equip].name; }
    this.ctx.talk(undefined, [`宝箱をあけた！ ${name}を手に入れた！`, ...(d.equip ? ['（メニューの「そうび」で装備しよう）'] : [])]);
  }

  private changeMap(to: string, x: number, y: number, dir: Dir): void {
    this.locked = true;
    this.cameras.main.fadeOut(200);
    this.cameras.main.once('camerafadeoutcomplete', () => {
      Object.assign(game.state, { map: to, x, y, dir });
      this.scene.restart({});
    });
  }

  startBattle(enemies: EnemyId[], opts: { boss?: boolean; onWin?: () => void }): void {
    this.locked = true;
    sfx.hit();
    this.cameras.main.flash(300, 255, 255, 255);
    this.tweens.add({ targets: this.cameras.main, zoom: 1.6, duration: 450, ease: 'Cubic.In' });
    this.time.delayedCall(480, () => {
      this.scene.start('RpgBattle', {
        enemies,
        boss: opts.boss,
        onWin: opts.onWin,
        background: ENCOUNTERS[this.map.encounter ?? 'field'].background,
      });
    });
  }

  private openMenu(): void {
    sfx.select();
    openFieldMenu(this, this.ui, () => undefined);
  }

  private showMapName(): void {
    const t = this.add.text(GAME_WIDTH / 2, 70, this.map.name, { fontFamily: FONT, fontSize: '28px', color: '#ffffff', backgroundColor: '#10184acc', padding: { x: 24, y: 8 } })
      .setOrigin(0.5).setScrollFactor(0).setDepth(2400).setAlpha(0);
    this.tweens.chain({ targets: t, tweens: [{ alpha: 1, duration: 300 }, { alpha: 1, duration: 1200 }, { alpha: 0, duration: 500, onComplete: () => t.destroy() }] });
  }

  private wander(): void {
    if (this.busy) return;
    const s = game.state;
    for (const n of this.npcs) {
      if (!n.def.wander || n.moving || Math.random() < 0.5) continue;
      const dir = (['up', 'down', 'left', 'right'] as Dir[])[Math.floor(Math.random() * 4)];
      const [dx, dy] = DIRV[dir];
      const nx = n.x + dx;
      const ny = n.y + dy;
      if (Math.abs(nx - n.def.x) > 2 || Math.abs(ny - n.def.y) > 2) continue;
      if (this.blocked(nx, ny) || (nx === s.x && ny === s.y)) continue;
      if (this.map.exits.some((e) => e.x === nx && e.y === ny)) continue;
      n.x = nx;
      n.y = ny;
      n.moving = true;
      n.sprite.setTexture(`${n.def.sprite}-${dir === 'left' || dir === 'right' ? 'side' : dir}`).setFlipX(dir === 'left').setDepth(ny + 0.5);
      this.tweens.add({ targets: n.sprite, x: (nx + 0.5) * RT, y: (ny + 0.5) * RT, duration: 260, onComplete: () => (n.moving = false) });
    }
  }

  /** イベントから使う機能 */
  private get ctx(): EventContext {
    return {
      state: game.state,
      say: (script: Script, onEnd?: () => void) => this.dialogue.start(script, { flags: game.state.flags, onEnd }),
      talk: (speaker, lines, onEnd) => {
        const script: Script = {};
        lines.forEach((text, i) => (script[i === 0 ? 'start' : `l${i}`] = { speaker, text, next: i < lines.length - 1 ? `l${i + 1}` : undefined }));
        this.dialogue.start(script, { flags: game.state.flags, onEnd });
      },
      openShop: () => openShop(this, this.ui, () => this.ctx.talk('道具屋', ['まいどあり！ またどうぞ。'])),
      rest: () => {
        this.locked = true;
        this.cameras.main.fadeOut(600);
        this.cameras.main.once('camerafadeoutcomplete', () => {
          healAll(game.state);
          sfx.powerup();
          this.time.delayedCall(500, () => {
            this.cameras.main.fadeIn(600);
            this.locked = false;
            this.ctx.talk('宿屋', ['おはようございます。よく眠れましたか？', '（HPとMPが全回復した）']);
          });
        });
      },
      battle: (enemies, opts) => this.startBattle(enemies, opts),
      refresh: () => {
        for (const n of [...this.npcs]) {
          if (n.def.hideIf && game.state.flags[n.def.hideIf]) {
            n.sprite.destroy();
            this.npcs = this.npcs.filter((x) => x !== n);
          }
        }
      },
      ending: () => {
        this.locked = true;
        this.cameras.main.fadeOut(1200, 255, 255, 255);
        this.cameras.main.once('camerafadeoutcomplete', () => this.scene.start('RpgEnding'));
      },
      healParty: () => {
        healAll(game.state);
        sfx.powerup();
        this.cameras.main.flash(300, 120, 220, 255);
      },
    };
  }
}

function tileAtChar(ch: string): number {
  return tileAt({ rows: [ch] } as MapDef, 0, 0)?.tile ?? 0;
}
