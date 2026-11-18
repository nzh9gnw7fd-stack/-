import type { EncounterId, EquipId, ItemId } from './data';
import type { Dir } from './state';
import { RTile } from './textures';

/**
 * マップは文字で描く。1文字 = 1タイル（32px）。
 *   .草  ,道  T木(通れない)  F森(通れる・敵が多い)  ^山  ~水  B橋  *花
 *   #壁  R屋根  =床  D扉  c カウンター（向こうの人と話せる）  o井戸
 *   V村  C洞窟の入口  :洞窟の床  X洞窟の壁  S階段  w回復の泉
 */
export const LEGEND: Record<string, { tile: number; solid?: boolean; encounter?: number }> = {
  '.': { tile: RTile.GRASS, encounter: 1 },
  ',': { tile: RTile.PATH },
  T: { tile: RTile.TREE, solid: true },
  F: { tile: RTile.TREE, encounter: 1.6 },
  '^': { tile: RTile.MOUNTAIN, solid: true },
  '~': { tile: RTile.WATER, solid: true },
  B: { tile: RTile.BRIDGE },
  '*': { tile: RTile.FLOWER },
  '#': { tile: RTile.WALL, solid: true },
  R: { tile: RTile.ROOF, solid: true },
  '=': { tile: RTile.FLOOR },
  D: { tile: RTile.DOOR },
  c: { tile: RTile.COUNTER, solid: true },
  o: { tile: RTile.WELL, solid: true },
  V: { tile: RTile.VILLAGE },
  C: { tile: RTile.CAVE },
  ':': { tile: RTile.CAVE_FLOOR, encounter: 1 },
  X: { tile: RTile.CAVE_WALL, solid: true },
  S: { tile: RTile.STAIRS },
  w: { tile: RTile.SPRING },
};

export interface NpcDef {
  id: string;
  x: number;
  y: number;
  sprite: string;
  dir?: Dir;
  /** ときどき歩き回る */
  wander?: boolean;
  /** 話しかけたときのイベント名（events.ts） */
  talk: string;
  /** このフラグが立っていたら消える */
  hideIf?: string;
  scale?: number;
}

export interface ChestDef {
  id: string;
  x: number;
  y: number;
  item?: ItemId;
  equip?: EquipId;
  gold?: number;
  count?: number;
}

export interface ExitDef { x: number; y: number; to: string; tx: number; ty: number; dir: Dir }

export interface TriggerDef { x: number; y: number; event: string }

export interface MapDef {
  id: string;
  name: string;
  rows: string[];
  music: 'town' | 'field' | 'cave';
  encounter?: EncounterId;
  /** 1歩あたりのエンカウント率 */
  rate?: number;
  npcs: NpcDef[];
  chests: ChestDef[];
  exits: ExitDef[];
  triggers: TriggerDef[];
}

const village: MapDef = {
  id: 'village',
  name: 'ハルナ村',
  music: 'town',
  rows: [
    'TTTTTTTTTTTTTTTTTTTTTTTTTT',
    'T........................T',
    'T.#######.......#######..T',
    'T.#=====#.......#=====#..T',
    'T.#=====#..***..#=====#..T',
    'T.#ccccc#..*o*..#ccccc#..T',
    'T.#=====#..***..#=====#..T',
    'T.###D###.......###D###..T',
    'T....,,,,,,,,,,,,,,,,....T',
    'T....,..........,...,....T',
    'T....,..#######.,...,....T',
    'T....,..#=====#.,...,....T',
    'T....,..#=====#.,...,....T',
    'T....,..###D###.,...,....T',
    'T....,,,,,,,,,,,,,,,,....T',
    'T..........,,............T',
    'T..***.....,,.......***..T',
    'T..........,,............T',
    'T..........,,............T',
    'TTTTTTTTTTT,,TTTTTTTTTTTTT',
  ],
  npcs: [
    { id: 'merchant', x: 5, y: 4, sprite: 'merchant', talk: 'shop' },
    { id: 'innkeeper', x: 19, y: 4, sprite: 'innkeeper', talk: 'inn' },
    { id: 'elder', x: 11, y: 11, sprite: 'elder', talk: 'elder' },
    { id: 'girl', x: 14, y: 6, sprite: 'girl', talk: 'girl', wander: true },
    { id: 'villager', x: 6, y: 16, sprite: 'villager', talk: 'villager', wander: true },
    { id: 'guard', x: 10, y: 18, sprite: 'guard', talk: 'guard' },
  ],
  chests: [
    { id: 'v-chest', x: 23, y: 1, item: 'herb', count: 2 },
  ],
  exits: [
    { x: 11, y: 19, to: 'field', tx: 7, ty: 24, dir: 'right' },
    { x: 12, y: 19, to: 'field', tx: 7, ty: 24, dir: 'right' },
  ],
  triggers: [],
};

const field: MapDef = {
  id: 'field',
  name: 'ミドリ平原',
  music: 'field',
  encounter: 'field',
  rate: 1 / 20,
  rows: [
    '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^',
    '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^',
    '^^^^^^^^^^^........~~.................^^',
    '^^^^^^^^^^^........~~.................^^',
    '^^^^^^^^^^.........~~......F..........^^',
    '^^^^^^^^^^.........~~....FFFFF...C....^^',
    '^^^^^^^^^..........~~...FFFFFFF..,....^^',
    '^^^^^^^^^..........~~...FFFFFFF..,....^^',
    '^^^^^^^^...........~~..FFFFFFFFF.,....^^',
    '^^..................~~..FFFFFFF,,,....^^',
    '^^..................~~..FFF,,,,,.F....^^',
    '^^......F...........~~...F,,FF.FFFFF..^^',
    '^^....FFFFF.........~~..,,,F...FFFFF..^^',
    '^^....FFFFF.........~~..,.....FFFFFFF.^^',
    '^^...FFFFFFF........~~,,,......FFFFF..^^',
    '^^....FFFFF.......,.BB,........FFFFF..^^',
    '^^....FFFFF.......,.~~...........F....^^',
    '^^......F.........,.~~................^^',
    '^^................,.~~...........^^^^^^^',
    '^^............F...,.~~...........^^^^^^^',
    '^^....F.....FFFFF.,~~....F......^^^^^^^^',
    '^^...FFF....FFFFF.,~~...FFF.....^^^^^^^^',
    '^^..FFFFF..FFFFFFF,~~..FFFFF....^^^^^^^^',
    '^^...FFF,,,,,,,,,,,~~...FFF....^^^^^^^^^',
    '^^....V,,...FFFFF..~~....F.....^^^^^^^^^',
    '^^............F....~~..........^^^^^^^^^',
    '^^.................~~.........^^^^^^^^^^',
    '^^.................~~.........^^^^^^^^^^',
    '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^',
    '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^',
  ],
  npcs: [
    { id: 'traveler', x: 22, y: 14, sprite: 'villager', talk: 'traveler', dir: 'left' },
  ],
  chests: [
    { id: 'f-chest1', x: 8, y: 14, gold: 80 },
    { id: 'f-chest2', x: 28, y: 8, item: 'ether' },
  ],
  exits: [
    { x: 6, y: 24, to: 'village', tx: 11, ty: 18, dir: 'up' },
    { x: 33, y: 5, to: 'cave', tx: 14, ty: 19, dir: 'up' },
  ],
  triggers: [],
};

const cave: MapDef = {
  id: 'cave',
  name: 'くらやみの洞窟',
  music: 'cave',
  encounter: 'cave',
  rate: 1 / 16,
  rows: [
    'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
    'XXXXXXXXXXX::::::::XXXXXXXXXXX',
    'XXXXXXXXXXX::::::::XXXXXXXXXXX',
    'XXXXXXXXXXX::::::::XXXXXXXXXXX',
    'XXXXXXXXXXXXXX::XXXXXXXXXXXXXX',
    'XXX:::::XXXXXX::XXXXXX::::::XX',
    'XXX:::::XXXXXXw:XXXXXX::::::XX',
    'XXX:::::::::::::::::::::::::XX',
    'XXX:::::XXXXXXXXXXXXXX::::::XX',
    'XXXX::XXXXXXXXXXXXXXXXXX::XXXX',
    'XXXX::XXXX::::::::XXXXXX::XXXX',
    'XXXX::XXXX::::::::XXXXXX::XXXX',
    'XXXX::::::::XXXX::::::::::XXXX',
    'XXXXXXXXXX::XXXX::XXXXXXXXXXXX',
    'XX:::::XXX::XXXX::XXX:::::::XX',
    'XX:::::::::::XX:::::::::::::XX',
    'XX:::::XXXXXXXX::XXX:::::::XXX',
    'XXXX:XXXXXXXXXX::XXXXXXXXXXXXX',
    'XXXX:::::::::::::XXXXXXXXXXXXX',
    'XXXXXXXXXXXXXX::XXXXXXXXXXXXXX',
    'XXXXXXXXXXXXXXSSXXXXXXXXXXXXXX',
    'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
  ],
  npcs: [
    { id: 'golem', x: 14, y: 2, sprite: 'e-golem', talk: 'boss', hideIf: 'bossDefeated', scale: 0.4 },
  ],
  chests: [
    { id: 'c-chest1', x: 4, y: 5, equip: 'steelSword' },
    { id: 'c-chest2', x: 27, y: 5, equip: 'chain' },
    { id: 'c-chest3', x: 11, y: 10, item: 'phoenix' },
    { id: 'c-chest4', x: 2, y: 14, gold: 200 },
    { id: 'c-chest5', x: 27, y: 14, item: 'ether', count: 2 },
  ],
  exits: [
    { x: 14, y: 20, to: 'field', tx: 33, ty: 6, dir: 'down' },
    { x: 15, y: 20, to: 'field', tx: 33, ty: 6, dir: 'down' },
  ],
  triggers: [
    { x: 14, y: 6, event: 'spring' },
    { x: 14, y: 4, event: 'bossRoom' },
    { x: 15, y: 4, event: 'bossRoom' },
  ],
};

export const MAPS: Record<string, MapDef> = { village, field, cave };

export function tileAt(map: MapDef, x: number, y: number): (typeof LEGEND)[string] | undefined {
  const ch = map.rows[y]?.[x];
  return ch === undefined ? undefined : LEGEND[ch];
}

export function isSolid(map: MapDef, x: number, y: number): boolean {
  const t = tileAt(map, x, y);
  return !t || !!t.solid;
}
