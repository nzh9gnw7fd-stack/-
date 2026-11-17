import { Map as RotMap, RNG } from 'rot-js';

/** ローグライク用のダンジョン生成（rot.js の Digger アルゴリズム）。0=壁, 1=床 */
export interface Dungeon {
  width: number;
  height: number;
  tiles: number[][];
  rooms: { x: number; y: number }[];
  start: { x: number; y: number };
  stairs: { x: number; y: number };
}

export function generateDungeon(width: number, height: number, seed: number): Dungeon {
  RNG.setSeed(seed);
  const tiles = Array.from({ length: height }, () => Array<number>(width).fill(0));
  const digger = new RotMap.Digger(width, height, { roomWidth: [4, 9], roomHeight: [3, 7], dugPercentage: 0.3 });
  digger.create((x, y, wall) => {
    tiles[y][x] = wall ? 0 : 1;
  });
  const rooms = digger.getRooms().map((room) => {
    const [x, y] = room.getCenter();
    return { x, y };
  });
  return { width, height, tiles, rooms, start: rooms[0], stairs: rooms[rooms.length - 1] };
}

/** 2点が床でつながっているか（幅優先探索） */
export function isConnected(d: Dungeon, a: { x: number; y: number }, b: { x: number; y: number }): boolean {
  const seen = new Set<string>([`${a.x},${a.y}`]);
  const queue = [a];
  while (queue.length) {
    const p = queue.shift()!;
    if (p.x === b.x && p.y === b.y) return true;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const x = p.x + dx;
      const y = p.y + dy;
      const k = `${x},${y}`;
      if (d.tiles[y]?.[x] === 1 && !seen.has(k)) {
        seen.add(k);
        queue.push({ x, y });
      }
    }
  }
  return false;
}
