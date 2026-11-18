import Phaser from 'phaser';
import { GAME_WIDTH } from '../../config';
import { GameInput } from '../../core/input';
import { sfx } from '../../core/sfx';
import { FONT } from '../../core/ui';
import { Battle, type Action, type BattleEvent, type Fighter } from '../battle';
import { ENEMIES, ITEMS, MEMBERS, SKILLS, type EnemyId, type ItemId, type SkillId } from '../data';
import { playMusic } from '../music';
import { START, game, gainExp, healAll, skillsOf } from '../state';
import { SelectList, UIStack, Win, type ListItem } from '../ui';
import type { MapSceneData } from './MapScene';

interface BattleData { enemies: EnemyId[]; boss?: boolean; onWin?: () => void; background: number }

/** ターン制バトルの画面。計算は battle.ts、ここは選択と演出。 */
export class BattleScene extends Phaser.Scene {
  private battle!: Battle;
  private data0!: BattleData;
  private controls!: GameInput;
  private ui!: UIStack;
  private msgWin!: Win;
  private msgText!: Phaser.GameObjects.Text;
  private statusWin!: Win;
  private enemySprites = new Map<string, Phaser.GameObjects.Image>();
  private actions: Action[] = [];
  private memberIndex = 0;
  private waiting: (() => void) | null = null;
  private targetMode: { onPick: (key: string) => void; index: number; arrow: Phaser.GameObjects.Image } | null = null;
  private activeKey: string | null = null;

  constructor() {
    super('RpgBattle');
  }

  init(data: BattleData): void {
    this.data0 = data;
    this.enemySprites.clear();
    this.actions = [];
    this.waiting = null;
    this.targetMode = null;
  }

  create(): void {
    const d = this.data0;
    this.battle = new Battle(game.state, d.enemies, { canFlee: !d.boss });
    this.controls = new GameInput(this);
    this.ui = new UIStack();

    // 背景
    const bg = this.add.graphics();
    const sky = Phaser.Display.Color.IntegerToColor(d.background);
    bg.fillStyle(sky.clone().darken(30).color).fillRect(0, 0, 800, 600);
    bg.fillStyle(d.background).fillRect(0, 300, 800, 300);
    bg.fillStyle(0x000000, 0.18).fillEllipse(400, 345, 760, 110);

    // 敵の配置
    const enemies = this.battle.enemies;
    const spacing = Math.min(220, 700 / enemies.length);
    enemies.forEach((e, i) => {
      const x = GAME_WIDTH / 2 + (i - (enemies.length - 1) / 2) * spacing;
      const sprite = this.add.image(x, 350, ENEMIES[e.enemy!].sprite).setOrigin(0.5, 1);
      sprite.setInteractive({ useHandCursor: true }).on('pointerdown', () => this.pickTargetByPointer(e.key));
      this.enemySprites.set(e.key, sprite);
      this.tweens.add({ targets: sprite, y: 344, duration: 900 + i * 120, yoyo: true, repeat: -1, ease: 'Sine.InOut' });
    });

    this.msgWin = new Win(this, 20, 16, 760, 84);
    this.msgText = this.msgWin.text(20, 16, '', 20);
    this.msgText.setWordWrapWidth(720);
    this.statusWin = new Win(this, 220, 446, 564, 140);
    this.refreshStatus();

    playMusic(d.boss ? 'boss' : 'battle');
    this.input.on('pointerdown', () => this.resolveWait());
    void this.run();
  }

  update(): void {
    if (this.waiting) {
      if (this.controls.actionPressed || this.controls.cancelPressed) this.resolveWait();
      return;
    }
    if (this.targetMode) {
      this.handleTargetInput();
      return;
    }
    this.ui.update(this.controls);
  }

  // ---------------- 流れ ----------------

  private async run(): Promise<void> {
    const names = [...new Set(this.battle.enemies.map((e) => ENEMIES[e.enemy!].name))].join('と');
    await this.say(this.data0.boss ? `${names}が立ちはだかった！` : `${names}があらわれた！`, 900);
    this.startCommands();
  }

  private startCommands(): void {
    this.actions = [];
    this.memberIndex = -1;
    this.nextMember();
  }

  /** 次の（生きている）仲間のコマンド入力へ */
  private nextMember(): void {
    const party = this.battle.party;
    do this.memberIndex++;
    while (this.memberIndex < party.length && party[this.memberIndex].hp <= 0);
    if (this.memberIndex >= party.length) {
      this.setActive(null);
      void this.playTurn();
      return;
    }
    this.showCommands(party[this.memberIndex]);
  }

  private prevMember(): void {
    const party = this.battle.party;
    let i = this.memberIndex - 1;
    while (i >= 0 && party[i].hp <= 0) i--;
    if (i < 0) return;
    this.ui.clear();
    this.actions.pop();
    this.memberIndex = i;
    this.showCommands(party[i]);
  }

  private choose(action: Action): void {
    this.actions.push(action);
    this.ui.clear();
    this.nextMember();
  }

  private showCommands(f: Fighter): void {
    this.setActive(f.key);
    this.setMessage(`${f.name}はどうする？`);
    const hasSkills = skillsOf(f.member!).length > 0;
    const list = new SelectList(this, 20, 404, 190, [
      { label: 'たたかう', onSelect: () => this.selectEnemy((t) => this.choose({ actor: f.key, kind: 'attack', target: t })) },
      { label: 'スキル', disabled: !hasSkills, onSelect: () => this.skillMenu(f) },
      { label: 'どうぐ', disabled: Object.keys(game.state.items).length === 0, onSelect: () => this.itemMenu(f) },
      { label: 'ぼうぎょ', onSelect: () => this.choose({ actor: f.key, kind: 'defend' }) },
      { label: 'にげる', disabled: !this.battle.opts.canFlee, onSelect: () => this.choose({ actor: f.key, kind: 'flee' }) },
    ], { rowHeight: 34 });
    list.onCancel = () => this.prevMember();
    this.ui.push(list);
  }

  private skillMenu(f: Fighter): void {
    const items: ListItem[] = skillsOf(f.member!).map((id: SkillId) => {
      const def = SKILLS[id];
      return {
        label: def.name,
        right: `MP${def.mp}`,
        disabled: f.mp < def.mp,
        onSelect: () => {
          const act = (target?: string) => this.choose({ actor: f.key, kind: 'skill', skill: id, target });
          if (def.target === 'enemy') this.selectEnemy(act);
          else if (def.target === 'ally') this.selectAlly('だれに？', (k) => act(k), (a) => a.hp > 0);
          else if (def.target === 'deadAlly') this.selectAlly('だれを？', (k) => act(k), (a) => a.hp <= 0);
          else act();
        },
      };
    });
    const list = new SelectList(this, 220, 250, 360, items, { title: 'スキル', visibleRows: 5 });
    list.onMove = (i) => this.setMessage(SKILLS[skillsOf(f.member!)[i]].desc);
    this.setMessage(SKILLS[skillsOf(f.member!)[0]].desc);
    list.onCancel = () => { this.ui.pop(); this.setMessage(`${f.name}はどうする？`); };
    this.ui.push(list);
  }

  private itemMenu(f: Fighter): void {
    // 同じターンにほかの仲間が使う予定の分を引いておく
    const reserved = (id: ItemId) => this.actions.filter((a) => a.kind === 'item' && a.item === id).length;
    const entries = (Object.entries(game.state.items) as [ItemId, number][]).map(([id, n]) => [id, n - reserved(id)] as const);
    const items: ListItem[] = entries.map(([id, n]) => ({
      label: ITEMS[id].name,
      right: `×${n}`,
      disabled: n <= 0,
      onSelect: () => {
        const dead = ITEMS[id].target === 'deadAlly';
        this.selectAlly('だれに？', (k) => this.choose({ actor: f.key, kind: 'item', item: id, target: k }), (a) => (dead ? a.hp <= 0 : a.hp > 0));
      },
    }));
    const list = new SelectList(this, 220, 250, 360, items, { title: 'どうぐ', visibleRows: 5 });
    list.onMove = (i) => this.setMessage(ITEMS[entries[i][0]].desc);
    if (entries[0]) this.setMessage(ITEMS[entries[0][0]].desc);
    list.onCancel = () => { this.ui.pop(); this.setMessage(`${f.name}はどうする？`); };
    this.ui.push(list);
  }

  private selectAlly(title: string, onPick: (key: string) => void, filter: (f: Fighter) => boolean): void {
    const items: ListItem[] = this.battle.party.map((p) => ({
      label: p.name,
      right: `HP ${p.hp}/${p.stats.maxHp}`,
      disabled: !filter(p),
      onSelect: () => onPick(p.key),
    }));
    const list = new SelectList(this, 300, 200, 300, items, { title });
    list.onCancel = () => this.ui.pop();
    this.ui.push(list);
  }

  /** 敵の頭上に矢印を出して、左右で選ぶ */
  private selectEnemy(onPick: (key: string) => void): void {
    const alive = this.battle.alive('enemy');
    const arrow = this.add.image(0, 0, 'target').setDepth(50);
    this.tweens.add({ targets: arrow, scaleY: 0.7, duration: 300, yoyo: true, repeat: -1 });
    this.targetMode = { onPick, index: 0, arrow };
    this.ui.top?.list?.setActive(false);
    this.moveTarget(0);
    void alive;
  }

  private moveTarget(delta: number): void {
    const tm = this.targetMode!;
    const alive = this.battle.alive('enemy');
    tm.index = Phaser.Math.Wrap(tm.index + delta, 0, alive.length);
    const sprite = this.enemySprites.get(alive[tm.index].key)!;
    tm.arrow.setPosition(sprite.x, sprite.y - sprite.displayHeight - 16);
    this.setMessage(`${alive[tm.index].name}（だれをこうげきする？）`);
  }

  private handleTargetInput(): void {
    const tm = this.targetMode!;
    const d = this.controls.dirPressed;
    if (d?.x || d?.y) { sfx.text(); this.moveTarget(d.x || d.y); }
    else if (this.controls.actionPressed) this.finishTarget(this.battle.alive('enemy')[tm.index].key);
    else if (this.controls.cancelPressed) {
      sfx.cancel();
      tm.arrow.destroy();
      this.targetMode = null;
      this.ui.top?.list?.setActive(true);
    }
  }

  private pickTargetByPointer(key: string): void {
    if (this.targetMode && this.battle.get(key).hp > 0) this.finishTarget(key);
  }

  private finishTarget(key: string): void {
    sfx.select();
    const tm = this.targetMode!;
    tm.arrow.destroy();
    this.targetMode = null;
    tm.onPick(key);
  }

  // ---------------- 演出 ----------------

  private async playTurn(): Promise<void> {
    const events = this.battle.runTurn(this.actions);
    for (const ev of events) await this.playEvent(ev);
    this.battle.commit();
    this.setActive(null);
    switch (this.battle.result) {
      case 'win': return this.victory();
      case 'lose': return this.defeat();
      case 'fled': return this.leave({ afterBattle: 'fled' });
      default: this.startCommands();
    }
  }

  private async playEvent(ev: BattleEvent): Promise<void> {
    switch (ev.t) {
      case 'msg':
        await this.say(ev.text, 650);
        return;
      case 'act': {
        const f = this.battle.get(ev.actor);
        if (f.side === 'party') this.setActive(f.key);
        else {
          this.setActive(null);
          const s = this.enemySprites.get(f.key);
          if (s) await new Promise<void>((r) => this.tweens.add({ targets: s, scale: s.scale * 1.08, duration: 100, yoyo: true, onComplete: () => r() }));
        }
        return;
      }
      case 'damage': {
        const f = this.battle.get(ev.target);
        sfx.hit();
        if (f.side === 'enemy') {
          const s = this.enemySprites.get(f.key)!;
          this.tweens.add({ targets: s, alpha: 0.2, duration: 60, yoyo: true, repeat: 2 });
          this.tweens.add({ targets: s, x: s.x + 8, duration: 40, yoyo: true, repeat: 2 });
          this.popNumber(s.x, s.y - s.displayHeight / 2, `${ev.amount}`, ev.crit ? '#ffeb3b' : '#ffffff');
        } else {
          this.cameras.main.shake(200, ev.amount > 30 ? 0.02 : 0.01);
          this.cameras.main.flash(120, 200, 0, 0);
          const i = this.battle.party.indexOf(f);
          this.popNumber(220 + 16 + i * 186 + 60, 450, `${ev.amount}`, '#ff8a80');
        }
        this.refreshStatus();
        return;
      }
      case 'heal':
      case 'revive':
      case 'mp': {
        sfx.powerup();
        const f = this.battle.get(ev.target);
        const i = this.battle.party.indexOf(f);
        if (i >= 0) this.popNumber(220 + 16 + i * 186 + 60, 450, `${ev.amount}`, ev.t === 'mp' ? '#82b1ff' : '#69f0ae');
        this.refreshStatus();
        return;
      }
      case 'miss':
        sfx.cancel();
        return;
      case 'down': {
        const f = this.battle.get(ev.target);
        if (f.side === 'enemy') {
          sfx.explode();
          const s = this.enemySprites.get(f.key)!;
          this.tweens.killTweensOf(s);
          this.tweens.add({ targets: s, alpha: 0, scaleY: 0.2, duration: 400 });
        }
        this.refreshStatus();
        return;
      }
      default:
    }
  }

  private async victory(): Promise<void> {
    playMusic('victory', false);
    const s = game.state;
    const r = this.battle.rewards();
    s.gold += r.gold;
    s.battles++;
    await this.say('魔物たちをやっつけた！', 0);
    await this.say(`${r.exp} のけいけんちと ${r.gold} ゴールドを手に入れた！`, 0);
    for (const m of s.party.filter((p) => p.hp > 0)) {
      for (const up of gainExp(m, r.exp)) {
        sfx.powerup();
        this.refreshStatus();
        await this.say(`${MEMBERS[m.id].name}はレベル ${up.level} にあがった！`, 0);
        for (const sk of up.learned) await this.say(`${MEMBERS[m.id].name}は「${SKILLS[sk].name}」をおぼえた！`, 0);
      }
    }
    for (const it of r.drops) {
      s.items[it] = (s.items[it] ?? 0) + 1;
      await this.say(`魔物は ${ITEMS[it].name} を落としていった！`, 0);
    }
    this.leave({ afterBattle: 'win', onWin: this.data0.onWin });
  }

  private async defeat(): Promise<void> {
    playMusic('cave');
    await this.say('全滅してしまった……。', 0);
    const s = game.state;
    s.gold = Math.floor(s.gold / 2);
    healAll(s);
    Object.assign(s, { ...START, map: 'village', x: 19, y: 6, dir: 'down' as const });
    this.leave({ afterBattle: 'lose' });
  }

  private leave(data: MapSceneData): void {
    this.cameras.main.fadeOut(300);
    this.cameras.main.once('camerafadeoutcomplete', () => this.scene.start('RpgMap', data));
  }

  // ---------------- 表示の部品 ----------------

  private setMessage(text: string): void {
    this.msgText.setText(text);
  }

  /** メッセージを表示して待つ。ms=0 ならボタンを押すまで待つ */
  private say(text: string, ms: number): Promise<void> {
    this.setMessage(text + (ms === 0 ? ' ▼' : ''));
    return new Promise((resolve) => {
      let done = false;
      const finish = () => { if (!done) { done = true; this.waiting = null; resolve(); } };
      this.waiting = finish;
      if (ms > 0) this.time.delayedCall(ms, finish);
    });
  }

  private resolveWait(): void {
    this.waiting?.();
  }

  private setActive(key: string | null): void {
    this.activeKey = key;
    this.refreshStatus();
  }

  private refreshStatus(): void {
    const w = this.statusWin;
    w.clear();
    this.battle.party.forEach((f, i) => {
      const x = 16 + i * 186;
      const active = f.key === this.activeKey;
      const dead = f.hp <= 0;
      if (active) {
        const hl = this.add.rectangle(x - 6, 8, 178, 124, 0xffffff, 0.12).setOrigin(0);
        w.root.add(hl);
      }
      w.text(x, 14, f.name, 21, dead ? '#ef5350' : active ? '#ffd54f' : '#ffffff');
      w.text(x, 50, `HP ${f.hp}/${f.stats.maxHp}`, 18, dead ? '#ef5350' : f.hp < f.stats.maxHp / 4 ? '#ffb74d' : '#ffffff');
      w.text(x, 78, `MP ${f.mp}/${f.stats.maxMp}`, 18);
      const ratio = Math.max(0, f.hp / f.stats.maxHp);
      const bar = this.add.rectangle(x, 106, 150 * ratio, 8, ratio < 0.25 ? 0xff7043 : 0x66bb6a).setOrigin(0);
      const barBg = this.add.rectangle(x, 106, 150, 8, 0x000000, 0.5).setOrigin(0);
      w.root.add([barBg, bar]);
    });
  }

  private popNumber(x: number, y: number, str: string, color: string): void {
    const t = this.add.text(x, y, str, { fontFamily: FONT, fontSize: '30px', color, fontStyle: 'bold', stroke: '#000000', strokeThickness: 5 })
      .setOrigin(0.5).setDepth(5000);
    this.tweens.add({ targets: t, y: y - 40, duration: 300, ease: 'Back.Out' });
    this.tweens.add({ targets: t, alpha: 0, delay: 700, duration: 300, onComplete: () => t.destroy() });
  }
}
