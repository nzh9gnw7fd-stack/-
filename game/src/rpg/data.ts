/**
 * RPG のゲームデータ。数値を変えるとバランス調整ができる。
 */
export type Stat = 'maxHp' | 'maxMp' | 'atk' | 'def' | 'mag' | 'agi';
export type Stats = Record<Stat, number>;

// キャラと装備はお互いを参照するので、ID を先に書いておく
export type MemberId = 'allen' | 'mia' | 'sera';
export type EquipId = 'woodSword' | 'ironSword' | 'steelSword' | 'woodStaff' | 'magicStaff' | 'mace' | 'cloth' | 'leather' | 'chain' | 'silkRobe';

export type Target = 'enemy' | 'allEnemies' | 'ally' | 'allAllies' | 'deadAlly' | 'self';

export interface SkillDef {
  name: string;
  mp: number;
  target: Target;
  /** physical: 攻撃力×power、magic: base + 魔力×power、heal: base + 魔力×power、revive: HP割合 */
  kind: 'physical' | 'magic' | 'heal' | 'revive';
  power: number;
  base?: number;
  desc: string;
}

const SKILLS_ = {
  slash: { name: 'パワースラッシュ', mp: 3, target: 'enemy', kind: 'physical', power: 1.7, desc: '力をこめた一撃' },
  sweep: { name: 'なぎはらい', mp: 6, target: 'allEnemies', kind: 'physical', power: 0.9, desc: '敵全体を切りつける' },
  fire: { name: 'ファイア', mp: 3, target: 'enemy', kind: 'magic', base: 10, power: 1.3, desc: '炎で敵1体を焼く' },
  blizzard: { name: 'ブリザド', mp: 7, target: 'allEnemies', kind: 'magic', base: 8, power: 1.0, desc: '吹雪で敵全体を攻撃' },
  thunder: { name: 'サンダー', mp: 9, target: 'enemy', kind: 'magic', base: 30, power: 2.0, desc: '雷で敵1体に大ダメージ' },
  heal: { name: 'ヒール', mp: 3, target: 'ally', kind: 'heal', base: 20, power: 1.5, desc: '味方1人のHPを回復' },
  healAll: { name: 'ヒールオール', mp: 9, target: 'allAllies', kind: 'heal', base: 15, power: 1.0, desc: '味方全員のHPを回復' },
  revive: { name: 'リヴァイブ', mp: 10, target: 'deadAlly', kind: 'revive', power: 0.5, desc: '倒れた味方を生き返らせる' },
  // 敵専用
  darkBall: { name: 'ダークボール', mp: 4, target: 'enemy', kind: 'magic', base: 8, power: 1.2, desc: '' },
  rockSlide: { name: 'いわなだれ', mp: 0, target: 'allEnemies', kind: 'physical', power: 0.8, desc: '' },
  tackle: { name: 'たいあたり', mp: 0, target: 'enemy', kind: 'physical', power: 1.5, desc: '' },
} satisfies Record<string, SkillDef>;
export type SkillId = keyof typeof SKILLS_;
export const SKILLS: Record<SkillId, SkillDef> = SKILLS_;

export interface MemberDef {
  name: string;
  job: string;
  base: Stats;
  growth: Stats;
  /** レベル → 覚える技 */
  learns: [number, SkillId][];
  weapon: EquipId | null;
  armor: EquipId | null;
  color: number;
}

const MEMBERS_ = {
  allen: {
    name: 'アレン', job: '剣士', color: 0x42a5f5,
    base: { maxHp: 38, maxMp: 6, atk: 11, def: 6, mag: 2, agi: 6 },
    growth: { maxHp: 9, maxMp: 2, atk: 3, def: 2, mag: 0.5, agi: 1 },
    learns: [[3, 'slash'], [6, 'sweep']],
    weapon: 'woodSword', armor: 'cloth',
  },
  mia: {
    name: 'ミア', job: '魔法使い', color: 0xef5350,
    base: { maxHp: 24, maxMp: 16, atk: 5, def: 3, mag: 11, agi: 8 },
    growth: { maxHp: 5, maxMp: 5, atk: 1, def: 1, mag: 3, agi: 1 },
    learns: [[1, 'fire'], [4, 'blizzard'], [7, 'thunder']],
    weapon: 'woodStaff', armor: 'cloth',
  },
  sera: {
    name: 'セラ', job: '僧侶', color: 0x66bb6a,
    base: { maxHp: 30, maxMp: 14, atk: 7, def: 5, mag: 8, agi: 5 },
    growth: { maxHp: 6, maxMp: 4, atk: 2, def: 2, mag: 2, agi: 1 },
    learns: [[1, 'heal'], [5, 'revive'], [6, 'healAll']],
    weapon: 'mace', armor: 'cloth',
  },
} satisfies Record<MemberId, MemberDef>;
export const MEMBERS: Record<MemberId, MemberDef> = MEMBERS_;
export const PARTY_ORDER: MemberId[] = ['allen', 'mia', 'sera'];

export interface ItemDef {
  name: string;
  price: number;
  target: 'ally' | 'deadAlly' | 'allAllies';
  effect: { hp?: number; mp?: number; revive?: number };
  desc: string;
}

const ITEMS_ = {
  herb: { name: 'やくそう', price: 30, target: 'ally', effect: { hp: 40 }, desc: 'HPを40回復' },
  potion: { name: 'いやしの水', price: 120, target: 'ally', effect: { hp: 150 }, desc: 'HPを150回復' },
  ether: { name: 'まほうの水', price: 100, target: 'ally', effect: { mp: 20 }, desc: 'MPを20回復' },
  phoenix: { name: 'ふっかつそう', price: 250, target: 'deadAlly', effect: { revive: 0.5 }, desc: '倒れた味方をHP半分で生き返らせる' },
} satisfies Record<string, ItemDef>;
export type ItemId = keyof typeof ITEMS_;
export const ITEMS: Record<ItemId, ItemDef> = ITEMS_;

export interface EquipDef {
  name: string;
  slot: 'weapon' | 'armor';
  price: number;
  bonus: Partial<Stats>;
  for: MemberId[];
}

const EQUIPS_ = {
  woodSword: { name: 'きのつるぎ', slot: 'weapon', price: 50, bonus: { atk: 3 }, for: ['allen'] },
  ironSword: { name: 'てつのつるぎ', slot: 'weapon', price: 180, bonus: { atk: 9 }, for: ['allen'] },
  steelSword: { name: 'はがねのつるぎ', slot: 'weapon', price: 600, bonus: { atk: 18 }, for: ['allen'] },
  woodStaff: { name: 'きのつえ', slot: 'weapon', price: 40, bonus: { atk: 1, mag: 2 }, for: ['mia', 'sera'] },
  magicStaff: { name: 'まどうのつえ', slot: 'weapon', price: 260, bonus: { atk: 2, mag: 8 }, for: ['mia', 'sera'] },
  mace: { name: 'メイス', slot: 'weapon', price: 60, bonus: { atk: 4 }, for: ['sera'] },
  cloth: { name: 'ぬののふく', slot: 'armor', price: 20, bonus: { def: 2 }, for: ['allen', 'mia', 'sera'] },
  leather: { name: 'かわのよろい', slot: 'armor', price: 120, bonus: { def: 6 }, for: ['allen', 'mia', 'sera'] },
  chain: { name: 'くさりかたびら', slot: 'armor', price: 320, bonus: { def: 11 }, for: ['allen', 'sera'] },
  silkRobe: { name: 'シルクのローブ', slot: 'armor', price: 280, bonus: { def: 8, mag: 3 }, for: ['mia', 'sera'] },
} satisfies Record<EquipId, EquipDef>;
export const EQUIPS: Record<EquipId, EquipDef> = EQUIPS_;

export interface EnemyDef {
  name: string;
  sprite: string;
  stats: Stats;
  exp: number;
  gold: number;
  skills?: { id: SkillId; chance: number }[];
  /** 何ターンごとに必ず使う技 */
  everyN?: { n: number; id: SkillId };
  boss?: boolean;
  drop?: { item: ItemId; chance: number };
}

const ENEMIES_ = {
  slime: { name: 'スライム', sprite: 'e-slime', stats: { maxHp: 16, maxMp: 0, atk: 9, def: 2, mag: 0, agi: 3 }, exp: 4, gold: 5, drop: { item: 'herb', chance: 0.15 } },
  bat: { name: 'おおこうもり', sprite: 'e-bat', stats: { maxHp: 12, maxMp: 0, atk: 10, def: 1, mag: 0, agi: 12 }, exp: 5, gold: 4 },
  boar: { name: 'あばれイノシシ', sprite: 'e-boar', stats: { maxHp: 30, maxMp: 0, atk: 14, def: 5, mag: 0, agi: 6 }, exp: 10, gold: 10, skills: [{ id: 'tackle', chance: 0.25 }] },
  goblin: { name: 'ゴブリン', sprite: 'e-goblin', stats: { maxHp: 48, maxMp: 0, atk: 22, def: 9, mag: 0, agi: 9 }, exp: 20, gold: 18, drop: { item: 'herb', chance: 0.25 } },
  skeleton: { name: 'がいこつへい', sprite: 'e-skeleton', stats: { maxHp: 60, maxMp: 0, atk: 26, def: 14, mag: 0, agi: 6 }, exp: 26, gold: 24 },
  darkMage: { name: 'やみまどうし', sprite: 'e-mage', stats: { maxHp: 40, maxMp: 30, atk: 12, def: 8, mag: 18, agi: 10 }, exp: 30, gold: 30, skills: [{ id: 'darkBall', chance: 0.6 }], drop: { item: 'ether', chance: 0.3 } },
  golem: {
    name: '岩喰いのヌシ', sprite: 'e-golem', boss: true,
    stats: { maxHp: 1150, maxMp: 0, atk: 44, def: 22, mag: 0, agi: 4 }, exp: 300, gold: 500,
    everyN: { n: 3, id: 'rockSlide' },
  },
} satisfies Record<string, EnemyDef>;
export type EnemyId = keyof typeof ENEMIES_;
export const ENEMIES: Record<EnemyId, EnemyDef> = ENEMIES_;

export interface EncounterTable {
  enemies: [EnemyId, number][]; // [敵, 出やすさ]
  maxGroup: number;
  background: number;
}

const ENCOUNTERS_ = {
  field: { enemies: [['slime', 5], ['bat', 3], ['boar', 2]], maxGroup: 3, background: 0x4a7a3a },
  cave: { enemies: [['goblin', 4], ['skeleton', 3], ['darkMage', 2], ['bat', 1]], maxGroup: 3, background: 0x2a2433 },
} satisfies Record<string, EncounterTable>;
export type EncounterId = keyof typeof ENCOUNTERS_;
export const ENCOUNTERS: Record<EncounterId, EncounterTable> = ENCOUNTERS_;

/** そのレベルになるのに必要な累計経験値 */
export function expForLevel(level: number): number {
  return level <= 1 ? 0 : Math.round(8 * Math.pow(level - 1, 2.2));
}

export const MAX_LEVEL = 30;

export const SHOP_ITEMS: ({ kind: 'item'; id: ItemId } | { kind: 'equip'; id: EquipId })[] = [
  { kind: 'item', id: 'herb' },
  { kind: 'item', id: 'ether' },
  { kind: 'item', id: 'potion' },
  { kind: 'item', id: 'phoenix' },
  { kind: 'equip', id: 'ironSword' },
  { kind: 'equip', id: 'magicStaff' },
  { kind: 'equip', id: 'leather' },
  { kind: 'equip', id: 'chain' },
  { kind: 'equip', id: 'silkRobe' },
];

export const INN_PRICE = 20;
