import { createNoise2D } from 'simplex-noise';
import { mulberry32 } from '../core/random';
import { T } from '../core/textures';

/** パーリン/シンプレックスノイズで地形を作る（RPG のフィールドやサンドボックス向け） */
export function generateTerrain(width: number, height: number, seed: number): number[][] {
  const noise = createNoise2D(mulberry32(seed));
  const map: number[][] = [];
  for (let y = 0; y < height; y++) {
    map.push([]);
    for (let x = 0; x < width; x++) {
      // 複数の細かさのノイズを重ねる（fBm）と自然な形になる
      let v = 0;
      let amp = 1;
      let freq = 1 / 40;
      for (let o = 0; o < 4; o++) {
        v += noise(x * freq, y * freq) * amp;
        amp *= 0.5;
        freq *= 2;
      }
      // 端を海にして島っぽくする
      const dx = x / width - 0.5;
      const dy = y / height - 0.5;
      v -= Math.hypot(dx, dy) * 1.6 - 0.3;
      if (x < 2 || y < 2 || x >= width - 2 || y >= height - 2) v = -1;
      map[y].push(v < -0.25 ? T.WATER : v < -0.15 ? T.SAND : v < 0.35 ? T.GRASS : v < 0.6 ? T.FOREST : T.MOUNTAIN);
    }
  }
  return map;
}

export function isWalkable(tile: number): boolean {
  return tile !== T.WATER && tile !== T.MOUNTAIN;
}

/** 中心から一番近い草地を探す（スタート地点用） */
export function findStart(map: number[][]): { x: number; y: number } {
  const cx = Math.floor(map[0].length / 2);
  const cy = Math.floor(map.length / 2);
  for (let r = 0; r < Math.max(cx, cy); r++) {
    for (let y = cy - r; y <= cy + r; y++) {
      for (let x = cx - r; x <= cx + r; x++) {
        if (map[y]?.[x] === T.GRASS) return { x, y };
      }
    }
  }
  return { x: cx, y: cy };
}
