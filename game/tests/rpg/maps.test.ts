import { describe, expect, it } from 'vitest';
import { ENCOUNTERS } from '../../src/rpg/data';
import { LEGEND, MAPS, isSolid, type MapDef } from '../../src/rpg/maps';
import { START } from '../../src/rpg/state';

/** (x,y) から歩いて行ける場所をすべて求める */
function reachable(map: MapDef, x: number, y: number): Set<string> {
  const seen = new Set([`${x},${y}`]);
  const q = [[x, y]];
  while (q.length) {
    const [cx, cy] = q.shift()!;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = cx + dx;
      const ny = cy + dy;
      const k = `${nx},${ny}`;
      if (!seen.has(k) && !isSolid(map, nx, ny)) {
        seen.add(k);
        q.push([nx, ny]);
      }
    }
  }
  return seen;
}

describe('マップ', () => {
  for (const map of Object.values(MAPS)) {
    describe(map.name, () => {
      it('長方形で、知らない文字を使っていない', () => {
        const w = map.rows[0].length;
        map.rows.forEach((r, i) => {
          expect(r.length, `${i} 行目`).toBe(w);
          for (const ch of r) expect(LEGEND[ch], `文字 "${ch}"`).toBeDefined();
        });
      });
      it('出口の行き先は存在し、着地点は歩ける', () => {
        for (const e of map.exits) {
          expect(isSolid(map, e.x, e.y)).toBe(false);
          const to = MAPS[e.to];
          expect(to).toBeDefined();
          expect(isSolid(to, e.tx, e.ty)).toBe(false);
        }
      });
      it('人・宝箱・イベントはすべて歩いてたどり着ける', () => {
        const entry = map.id === START.map ? [START.x, START.y] : (() => {
          const from = Object.values(MAPS).flatMap((m) => m.exits).find((e) => e.to === map.id)!;
          return [from.tx, from.ty];
        })();
        const r = reachable(map, entry[0], entry[1]);
        const near = (x: number, y: number) => [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1], [0, 2]].some(([dx, dy]) => r.has(`${x + dx},${y + dy}`));
        for (const e of map.exits) expect(r.has(`${e.x},${e.y}`), `出口 ${e.x},${e.y}`).toBe(true);
        for (const t of map.triggers) expect(r.has(`${t.x},${t.y}`), `イベント ${t.event}`).toBe(true);
        for (const c of map.chests) expect(near(c.x, c.y), `宝箱 ${c.id}`).toBe(true);
        for (const n of map.npcs) expect(near(n.x, n.y), `人 ${n.id}`).toBe(true);
      });
      it('エンカウント設定が正しい', () => {
        if (map.encounter) expect(ENCOUNTERS[map.encounter]).toBeDefined();
      });
    });
  }
});
