/**
 * ターン制バトルの計算エンジン（描画とは独立）。
 * runTurn() にパーティの行動を渡すと、そのターンに起きた出来事（BattleEvent）の列を返す。
 * 画面側はそれを順番に演出するだけでよい。
 */
import { ENEMIES, ITEMS, MEMBERS, SKILLS, type EnemyId, type ItemId, type SkillId, type Stats } from './data';
import { removeItem, stats, type GameState, type Member } from './state';

export interface Fighter {
  key: string;
  name: string;
  side: 'party' | 'enemy';
  stats: Stats;
  hp: number;
  mp: number;
  defending: boolean;
  member?: Member;
  enemy?: EnemyId;
}

export type Command =
  | { kind: 'attack'; target: string }
  | { kind: 'skill'; skill: SkillId; target?: string }
  | { kind: 'item'; item: ItemId; target: string }
  | { kind: 'defend' }
  | { kind: 'flee' };

export type Action = Command & { actor: string };

export type BattleEvent =
  | { t: 'msg'; text: string }
  | { t: 'act'; actor: string }
  | { t: 'damage'; target: string; amount: number; crit?: boolean }
  | { t: 'heal'; target: string; amount: number }
  | { t: 'mp'; target: string; amount: number }
  | { t: 'revive'; target: string; amount: number }
  | { t: 'miss'; target: string }
  | { t: 'down'; target: string }
  | { t: 'fled' };

export type Result = 'ongoing' | 'win' | 'lose' | 'fled';

export interface Rewards { exp: number; gold: number; drops: ItemId[] }

export class Battle {
  readonly fighters: Fighter[];
  result: Result = 'ongoing';
  turn = 0;

  constructor(
    private readonly state: GameState,
    enemies: EnemyId[],
    readonly opts: { canFlee: boolean } = { canFlee: true },
    private readonly rng: () => number = Math.random,
  ) {
    const party: Fighter[] = state.party.map((m) => ({
      key: m.id, name: MEMBERS[m.id].name, side: 'party', stats: stats(m), hp: m.hp, mp: m.mp, defending: false, member: m,
    }));
    // 同じ敵が複数いたら A, B, C… を付ける
    const counts = new Map<EnemyId, number>();
    enemies.forEach((e) => counts.set(e, (counts.get(e) ?? 0) + 1));
    const seen = new Map<EnemyId, number>();
    const foes: Fighter[] = enemies.map((e, i) => {
      const n = seen.get(e) ?? 0;
      seen.set(e, n + 1);
      const def = ENEMIES[e];
      const suffix = (counts.get(e) ?? 0) > 1 ? 'ABCDEF'[n] : '';
      return { key: `e${i}`, name: def.name + suffix, side: 'enemy', stats: { ...def.stats }, hp: def.stats.maxHp, mp: def.stats.maxMp, defending: false, enemy: e };
    });
    this.fighters = [...party, ...foes];
  }

  get party(): Fighter[] { return this.fighters.filter((f) => f.side === 'party'); }
  get enemies(): Fighter[] { return this.fighters.filter((f) => f.side === 'enemy'); }
  get(key: string): Fighter { return this.fighters.find((f) => f.key === key)!; }
  alive(side: 'party' | 'enemy'): Fighter[] { return this.fighters.filter((f) => f.side === side && f.hp > 0); }

  /** 1ターン分を処理する */
  runTurn(partyActions: Action[]): BattleEvent[] {
    if (this.result !== 'ongoing') return [];
    this.turn++;
    const ev: BattleEvent[] = [];
    const actions = [...partyActions, ...this.enemyActions()];
    for (const f of this.fighters) f.defending = false;
    for (const a of actions) if (a.kind === 'defend') this.get(a.actor).defending = true;

    // 素早さ（＋ゆらぎ）の高い順に行動
    const order = actions
      .map((a) => ({ a, speed: this.get(a.actor).stats.agi * (0.8 + this.rng() * 0.4) }))
      .sort((x, y) => y.speed - x.speed)
      .map((x) => x.a);

    for (const a of order) {
      const actor = this.get(a.actor);
      if (actor.hp <= 0) continue;
      this.resolve(actor, a, ev);
      if ((this.result as Result) === 'fled') break;
      if (this.alive('enemy').length === 0) { this.result = 'win'; break; }
      if (this.alive('party').length === 0) { this.result = 'lose'; break; }
    }
    return ev;
  }

  /** 勝ったときの報酬 */
  rewards(): Rewards {
    let exp = 0;
    let gold = 0;
    const drops: ItemId[] = [];
    for (const e of this.enemies) {
      const def = ENEMIES[e.enemy!];
      exp += def.exp;
      gold += def.gold;
      if (def.drop && this.rng() < def.drop.chance) drops.push(def.drop.item);
    }
    return { exp, gold, drops };
  }

  /** HP/MP をゲームの状態に書き戻す */
  commit(): void {
    for (const f of this.party) {
      f.member!.hp = Math.max(0, f.hp);
      f.member!.mp = f.mp;
    }
  }

  private enemyActions(): Action[] {
    return this.alive('enemy').map((e) => {
      const def = ENEMIES[e.enemy!];
      const target = this.randomPartyTarget().key;
      if (def.everyN && this.turn % def.everyN.n === 0) return { actor: e.key, kind: 'skill', skill: def.everyN.id, target };
      for (const s of def.skills ?? []) {
        if (this.rng() < s.chance && e.mp >= SKILLS[s.id].mp) return { actor: e.key, kind: 'skill', skill: s.id, target };
      }
      return { actor: e.key, kind: 'attack', target };
    });
  }

  private randomPartyTarget(): Fighter {
    const alive = this.alive('party');
    // 先頭のキャラほど狙われやすい
    const weights = alive.map((_, i) => (i === 0 ? 1.5 : 1));
    let r = this.rng() * weights.reduce((a, b) => a + b, 0);
    for (let i = 0; i < alive.length; i++) {
      r -= weights[i];
      if (r <= 0) return alive[i];
    }
    return alive[alive.length - 1];
  }

  /** 狙った相手が倒れていたら、同じ側の別の相手にする */
  private retarget(key: string | undefined, side: 'party' | 'enemy'): Fighter | null {
    const t = key ? this.get(key) : undefined;
    if (t && t.hp > 0) return t;
    return this.alive(side)[0] ?? null;
  }

  private resolve(actor: Fighter, a: Action, ev: BattleEvent[]): void {
    const foeSide = actor.side === 'party' ? 'enemy' : 'party';
    const allySide = actor.side;
    switch (a.kind) {
      case 'defend':
        ev.push({ t: 'act', actor: actor.key }, { t: 'msg', text: `${actor.name}は身を守っている。` });
        return;
      case 'flee': {
        ev.push({ t: 'act', actor: actor.key });
        if (!this.opts.canFlee) {
          ev.push({ t: 'msg', text: 'にげられない！' });
          return;
        }
        if (this.rng() < 0.5 + 0.15 * (this.turn - 1)) {
          ev.push({ t: 'msg', text: `${actor.name}たちは逃げ出した！` }, { t: 'fled' });
          this.result = 'fled';
        } else {
          ev.push({ t: 'msg', text: 'しかし、まわりこまれてしまった！' });
        }
        return;
      }
      case 'attack': {
        const target = this.retarget(a.target, foeSide);
        if (!target) return;
        ev.push({ t: 'act', actor: actor.key }, { t: 'msg', text: `${actor.name}のこうげき！` });
        this.physical(actor, target, 1, ev, true);
        return;
      }
      case 'item': {
        const def = ITEMS[a.item];
        ev.push({ t: 'act', actor: actor.key });
        if (!removeItem(this.state, a.item)) {
          ev.push({ t: 'msg', text: `${def.name}はもうなかった！` });
          return;
        }
        ev.push({ t: 'msg', text: `${actor.name}は${def.name}を使った！` });
        const target = this.get(a.target);
        if (def.effect.revive) {
          if (target.hp > 0) { ev.push({ t: 'msg', text: 'しかし、何も起こらなかった。' }); return; }
          this.revive(target, def.effect.revive, ev);
        } else {
          const t = target.hp > 0 ? target : this.retarget(undefined, allySide);
          if (!t) return;
          if (def.effect.hp) this.heal(t, def.effect.hp, ev);
          if (def.effect.mp) {
            const amount = Math.min(def.effect.mp, t.stats.maxMp - t.mp);
            t.mp += amount;
            ev.push({ t: 'mp', target: t.key, amount }, { t: 'msg', text: `${t.name}のMPが ${amount} 回復した！` });
          }
        }
        return;
      }
      case 'skill': {
        const def = SKILLS[a.skill];
        ev.push({ t: 'act', actor: actor.key });
        if (actor.mp < def.mp) {
          ev.push({ t: 'msg', text: `${actor.name}は${def.name}をとなえようとした！ しかしMPがたりない！` });
          return;
        }
        actor.mp -= def.mp;
        ev.push({ t: 'msg', text: actor.side === 'party' && def.kind !== 'physical' ? `${actor.name}は${def.name}をとなえた！` : `${actor.name}の${def.name}！` });
        const targets: Fighter[] = (() => {
          switch (def.target) {
            case 'allEnemies': return this.alive(foeSide);
            case 'allAllies': return this.alive(allySide);
            case 'deadAlly': return [this.get(a.target!)].filter((f) => f.hp <= 0);
            case 'ally': { const t = this.retarget(a.target, allySide); return t ? [t] : []; }
            case 'self': return [actor];
            default: { const t = this.retarget(a.target, foeSide); return t ? [t] : []; }
          }
        })();
        if (targets.length === 0) { ev.push({ t: 'msg', text: 'しかし、何も起こらなかった。' }); return; }
        for (const t of targets) {
          if (t.hp <= 0 && def.kind !== 'revive') continue;
          switch (def.kind) {
            case 'physical': this.physical(actor, t, def.power, ev, false); break;
            case 'magic': this.magic(actor, t, (def.base ?? 0) + actor.stats.mag * def.power, ev); break;
            case 'heal': this.heal(t, Math.round((def.base ?? 0) + actor.stats.mag * def.power), ev); break;
            case 'revive': this.revive(t, def.power, ev); break;
          }
        }
      }
    }
  }

  private variance(): number { return 0.85 + this.rng() * 0.3; }

  private physical(actor: Fighter, target: Fighter, power: number, ev: BattleEvent[], canMiss: boolean): void {
    if (canMiss && this.rng() < 0.04) { ev.push({ t: 'miss', target: target.key }, { t: 'msg', text: `ミス！ ${target.name}はひらりとかわした！` }); return; }
    const crit = this.rng() < 0.06;
    let dmg = crit ? actor.stats.atk * power * 1.5 : (actor.stats.atk * power - target.stats.def * 0.5) * this.variance();
    if (target.defending) dmg /= 2;
    this.damage(target, Math.max(1, Math.round(dmg)), ev, crit);
  }

  private magic(_actor: Fighter, target: Fighter, power: number, ev: BattleEvent[]): void {
    let dmg = (power - target.stats.def * 0.25) * this.variance();
    if (target.defending) dmg /= 2;
    this.damage(target, Math.max(1, Math.round(dmg)), ev, false);
  }

  private damage(target: Fighter, amount: number, ev: BattleEvent[], crit: boolean): void {
    target.hp = Math.max(0, target.hp - amount);
    if (crit) ev.push({ t: 'msg', text: 'かいしんの一撃！' });
    ev.push({ t: 'damage', target: target.key, amount, crit }, { t: 'msg', text: `${target.name}に ${amount} のダメージ！` });
    if (target.hp === 0) ev.push({ t: 'down', target: target.key }, { t: 'msg', text: target.side === 'enemy' ? `${target.name}をたおした！` : `${target.name}は倒れてしまった…` });
  }

  private heal(target: Fighter, amount: number, ev: BattleEvent[]): void {
    const real = Math.min(amount, target.stats.maxHp - target.hp);
    target.hp += real;
    ev.push({ t: 'heal', target: target.key, amount: real }, { t: 'msg', text: `${target.name}のHPが ${real} 回復した！` });
  }

  private revive(target: Fighter, ratio: number, ev: BattleEvent[]): void {
    const amount = Math.max(1, Math.floor(target.stats.maxHp * ratio));
    target.hp = amount;
    ev.push({ t: 'revive', target: target.key, amount }, { t: 'msg', text: `${target.name}は生き返った！` });
  }
}

/** 出現テーブルから敵の組み合わせを選ぶ */
export function rollEncounter(table: { enemies: [EnemyId, number][]; maxGroup: number }, rng: () => number = Math.random): EnemyId[] {
  const total = table.enemies.reduce((s, [, w]) => s + w, 0);
  const pick = (): EnemyId => {
    let r = rng() * total;
    for (const [id, w] of table.enemies) {
      r -= w;
      if (r <= 0) return id;
    }
    return table.enemies[0][0];
  };
  const n = 1 + Math.floor(rng() * table.maxGroup);
  return Array.from({ length: n }, pick);
}
