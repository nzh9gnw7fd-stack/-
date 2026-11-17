import { describe, expect, it } from 'vitest';
import { T } from '../src/core/textures';
import { generateDungeon, isConnected } from '../src/logic/dungeon';
import { findStart, generateTerrain, isWalkable } from '../src/logic/terrain';

describe('ダンジョン生成', () => {
  it('スタートと階段が床で、つながっている', () => {
    for (let seed = 1; seed <= 10; seed++) {
      const d = generateDungeon(50, 36, seed);
      expect(d.tiles[d.start.y][d.start.x]).toBe(1);
      expect(d.tiles[d.stairs.y][d.stairs.x]).toBe(1);
      expect(isConnected(d, d.start, d.stairs)).toBe(true);
    }
  });
  it('同じシードなら同じダンジョン', () => {
    expect(generateDungeon(30, 20, 7).tiles).toEqual(generateDungeon(30, 20, 7).tiles);
  });
});

describe('地形生成', () => {
  it('同じシードなら同じ地形、違うシードなら違う地形', () => {
    expect(generateTerrain(40, 40, 1)).toEqual(generateTerrain(40, 40, 1));
    expect(generateTerrain(40, 40, 1)).not.toEqual(generateTerrain(40, 40, 2));
  });
  it('スタート地点は歩ける草地', () => {
    for (let seed = 1; seed <= 10; seed++) {
      const m = generateTerrain(120, 120, seed);
      const s = findStart(m);
      expect(m[s.y][s.x]).toBe(T.GRASS);
      expect(isWalkable(m[s.y][s.x])).toBe(true);
    }
  });
  it('外周は海', () => {
    const m = generateTerrain(120, 120, 3);
    expect(m[0].every((t) => t === T.WATER)).toBe(true);
  });
});
