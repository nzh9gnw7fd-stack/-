import { loadData, saveData, type KeyValueStorage } from '../core/save';
import {
  EQUIPS, ITEMS, MAX_LEVEL, MEMBERS, PARTY_ORDER, SKILLS, expForLevel,
  type EquipId, type ItemId, type MemberId, type SkillId, type Stat, type Stats,
} from './data';

export interface Member {
  id: MemberId;
  level: number;
  exp: number;
  hp: number;
  mp: number;
  weapon: EquipId | null;
  armor: EquipId | null;
}

export interface GameState {
  version: 1;
  party: Member[];
  gold: number;
  items: Partial<Record<ItemId, number>>;
  equips: Partial<Record<EquipId, number>>;
  flags: Record<string, boolean | number | string>;
  map: string;
  x: number;
  y: number;
  dir: Dir;
  steps: number;
  battles: number;
  playMs: number;
}

export type Dir = 'up' | 'down' | 'left' | 'right';

export const START = { map: 'village', x: 12, y: 15 };

export function newGame(): GameState {
  return {
    version: 1,
    party: PARTY_ORDER.map((id) => {
      const def = MEMBERS[id];
      const m: Member = { id, level: 1, exp: 0, hp: 0, mp: 0, weapon: def.weapon, armor: def.armor };
      const s = stats(m);
      m.hp = s.maxHp;
      m.mp = s.maxMp;
      return m;
    }),
    gold: 100,
    items: { herb: 3 },
    equips: {},
    flags: {},
    ...START,
    dir: 'down',
    steps: 0,
    battles: 0,
    playMs: 0,
  };
}

/** レベルと装備を反映した能力値 */
export function stats(m: Member): Stats {
  const def = MEMBERS[m.id];
  const out = {} as Stats;
  for (const k of Object.keys(def.base) as Stat[]) out[k] = Math.floor(def.base[k] + def.growth[k] * (m.level - 1));
  for (const e of [m.weapon, m.armor]) {
    if (!e) continue;
    for (const [k, v] of Object.entries(EQUIPS[e].bonus)) out[k as Stat] += v;
  }
  return out;
}

export function skillsOf(m: Member): SkillId[] {
  return MEMBERS[m.id].learns.filter(([lv]) => m.level >= lv).map(([, id]) => id);
}

export interface LevelUp { member: MemberId; level: number; learned: SkillId[] }

/** 経験値を足してレベルアップを処理する。上がった分の情報を返す */
export function gainExp(m: Member, exp: number): LevelUp[] {
  const ups: LevelUp[] = [];
  m.exp += exp;
  while (m.level < MAX_LEVEL && m.exp >= expForLevel(m.level + 1)) {
    const before = stats(m);
    const oldSkills = skillsOf(m);
    m.level++;
    const after = stats(m);
    // 増えた最大値の分だけ現在値も増やす
    if (m.hp > 0) m.hp += after.maxHp - before.maxHp;
    m.mp += after.maxMp - before.maxMp;
    ups.push({ member: m.id, level: m.level, learned: skillsOf(m).filter((s) => !oldSkills.includes(s)) });
  }
  return ups;
}

export function healAll(state: GameState): void {
  for (const m of state.party) {
    const s = stats(m);
    m.hp = s.maxHp;
    m.mp = s.maxMp;
  }
}

export function addItem(state: GameState, id: ItemId, n = 1): void {
  state.items[id] = (state.items[id] ?? 0) + n;
}

export function removeItem(state: GameState, id: ItemId, n = 1): boolean {
  const have = state.items[id] ?? 0;
  if (have < n) return false;
  if (have === n) delete state.items[id];
  else state.items[id] = have - n;
  return true;
}

export function addEquip(state: GameState, id: EquipId, n = 1): void {
  state.equips[id] = (state.equips[id] ?? 0) + n;
}

/** 装備する（null ではずす）。持ち物と入れ替える */
export function equip(state: GameState, m: Member, slot: 'weapon' | 'armor', id: EquipId | null): boolean {
  if (id) {
    const def = EQUIPS[id];
    if (def.slot !== slot || !(def.for as MemberId[]).includes(m.id) || !state.equips[id]) return false;
    state.equips[id]! -= 1;
    if (state.equips[id] === 0) delete state.equips[id];
  }
  const old = m[slot];
  if (old) addEquip(state, old);
  m[slot] = id;
  // 最大値が下がったら現在値を合わせる
  const s = stats(m);
  m.hp = Math.min(m.hp, s.maxHp);
  m.mp = Math.min(m.mp, s.maxMp);
  return true;
}

/** 道具を使う（フィールド用）。成功したら効果の説明を返す */
export function useItemOn(state: GameState, id: ItemId, m: Member): string | null {
  const def = ITEMS[id];
  const s = stats(m);
  const name = MEMBERS[m.id].name;
  if (!state.items[id]) return null;
  if (def.effect.revive) {
    if (m.hp > 0) return null;
    m.hp = Math.max(1, Math.floor(s.maxHp * def.effect.revive));
  } else {
    if (m.hp <= 0) return null;
    if (def.effect.hp && m.hp >= s.maxHp && !def.effect.mp) return null;
    if (def.effect.mp && m.mp >= s.maxMp && !def.effect.hp) return null;
    if (def.effect.hp) m.hp = Math.min(s.maxHp, m.hp + def.effect.hp);
    if (def.effect.mp) m.mp = Math.min(s.maxMp, m.mp + def.effect.mp);
  }
  removeItem(state, id);
  return def.effect.revive ? `${name}は生き返った！` : `${name}は回復した！`;
}

/** フィールドで回復魔法を使う */
export function castFieldSkill(caster: Member, skill: SkillId, target: Member, party: Member[]): string | null {
  const def = SKILLS[skill];
  if (caster.hp <= 0 || caster.mp < def.mp) return null;
  const mag = stats(caster).mag;
  const targets = def.target === 'allAllies' ? party.filter((p) => p.hp > 0) : [target];
  if (def.kind === 'heal') {
    if (def.target !== 'allAllies' && target.hp <= 0) return null;
    const amount = Math.round((def.base ?? 0) + mag * def.power);
    for (const t of targets) t.hp = Math.min(stats(t).maxHp, t.hp + amount);
  } else if (def.kind === 'revive') {
    if (target.hp > 0) return null;
    target.hp = Math.max(1, Math.floor(stats(target).maxHp * def.power));
  } else {
    return null;
  }
  caster.mp -= def.mp;
  return `${MEMBERS[caster.id].name}は${def.name}をとなえた！`;
}

// ---- セーブ / ロード ----
const SAVE_KEY = 'rpg.save';

export function saveGame(state: GameState, storage?: KeyValueStorage): boolean {
  return storage ? saveData(SAVE_KEY, state, storage) : saveData(SAVE_KEY, state);
}

export function loadGame(storage?: KeyValueStorage): GameState | null {
  const data = storage ? loadData<GameState | null>(SAVE_KEY, null, storage) : loadData<GameState | null>(SAVE_KEY, null);
  if (!data || data.version !== 1 || !Array.isArray(data.party)) return null;
  return data;
}

/** いま遊んでいるデータ（シーン間で共有） */
let current: GameState = newGame();
export const game = {
  get state(): GameState {
    return current;
  },
  set(state: GameState): void {
    current = state;
  },
};
