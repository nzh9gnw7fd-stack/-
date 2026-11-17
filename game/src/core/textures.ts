import type Phaser from 'phaser';
import { TILE } from '../config';

/** タイルセット内の番号（タイルマップのデータで使う） */
export const T = {
  GROUND: 0, BRICK: 1, WATER: 2, SAND: 3, GRASS: 4, FOREST: 5, MOUNTAIN: 6, WALL: 7, FLOOR: 8, STAIRS: 9,
} as const;

export const GEM_COLORS = [0xef5350, 0x42a5f5, 0x66bb6a, 0xffca28, 0xab47bc, 0xffffff];

/**
 * 画像ファイルなしで遊べるよう、図形からテクスチャを作る。
 * 自分の絵を使うときは BootScene の preload() で同じキー名の画像を読み込めば置き換わる
 * （すでにそのキーがあれば、ここでは作らない）。
 */
export function createPlaceholderTextures(scene: Phaser.Scene): void {
  const make = (key: string, w: number, h: number, draw: (g: Phaser.GameObjects.Graphics) => void) => {
    if (scene.textures.exists(key)) return;
    const g = scene.make.graphics({ x: 0, y: 0 }, false);
    draw(g);
    g.generateTexture(key, w, h);
    g.destroy();
  };
  const face = (g: Phaser.GameObjects.Graphics, color: number) => {
    g.fillStyle(color).fillRoundedRect(0, 0, 32, 32, 7);
    g.fillStyle(0xffffff).fillCircle(10, 12, 4).fillCircle(22, 12, 4);
    g.fillStyle(0x1d2033).fillCircle(11, 13, 2).fillCircle(23, 13, 2);
  };

  make('player', 32, 32, (g) => face(g, 0x4fc3f7));
  make('npc', 32, 32, (g) => face(g, 0x81c784));
  make('enemy', 32, 32, (g) => {
    face(g, 0xe57373);
    g.fillStyle(0x1d2033).fillTriangle(5, 5, 14, 9, 6, 11).fillTriangle(27, 5, 18, 9, 26, 11);
  });
  make('coin', 20, 20, (g) => {
    g.fillStyle(0xffd54f).fillCircle(10, 10, 10);
    g.fillStyle(0xffecb3).fillCircle(7, 7, 3);
  });
  make('spike', 32, 32, (g) => {
    g.fillStyle(0xb0bec5);
    for (let i = 0; i < 4; i++) g.fillTriangle(i * 8, 32, i * 8 + 4, 12, i * 8 + 8, 32);
  });
  make('flag', 32, 96, (g) => {
    g.fillStyle(0xeceff1).fillRect(4, 0, 4, 96);
    g.fillStyle(0x66bb6a).fillTriangle(8, 4, 30, 14, 8, 24);
  });
  make('ship', 36, 36, (g) => {
    g.fillStyle(0x4fc3f7).fillTriangle(18, 0, 36, 36, 0, 36);
    g.fillStyle(0xffffff).fillCircle(18, 22, 5);
  });
  make('ufo', 36, 24, (g) => {
    g.fillStyle(0xe57373).fillEllipse(18, 15, 36, 14);
    g.fillStyle(0xffcdd2).fillEllipse(18, 8, 16, 12);
  });
  make('bullet', 6, 16, (g) => g.fillStyle(0xfff59d).fillRoundedRect(0, 0, 6, 16, 3));
  make('ebullet', 10, 10, (g) => g.fillStyle(0xff8a65).fillCircle(5, 5, 5));
  make('particle', 8, 8, (g) => g.fillStyle(0xffffff).fillCircle(4, 4, 4));
  make('box', 40, 40, (g) => {
    g.fillStyle(0xa1887f).fillRect(0, 0, 40, 40);
    g.lineStyle(3, 0x6d4c41).strokeRect(2, 2, 36, 36).lineBetween(2, 2, 38, 38);
  });
  make('ball', 30, 30, (g) => {
    g.fillStyle(0x90a4ae).fillCircle(15, 15, 15);
    g.fillStyle(0xeceff1).fillCircle(10, 10, 4);
  });
  GEM_COLORS.forEach((color, i) => {
    make(`gem${i}`, 56, 56, (g) => {
      g.fillStyle(color);
      switch (i % 3) {
        case 0: g.fillCircle(28, 28, 24); break;
        case 1: g.fillRoundedRect(6, 6, 44, 44, 10); break;
        default: g.fillTriangle(28, 4, 52, 50, 4, 50);
      }
      g.fillStyle(0xffffff, 0.45).fillCircle(20, 20, 6);
    });
  });

  // タイルセット（横一列に TILE x TILE のタイルを並べる）
  make('tiles', TILE * 10, TILE, (g) => {
    const tile = (i: number, base: number, draw?: (x: number) => void) => {
      g.fillStyle(base).fillRect(i * TILE, 0, TILE, TILE);
      draw?.(i * TILE);
    };
    tile(T.GROUND, 0x8d6e63, (x) => g.fillStyle(0x66bb6a).fillRect(x, 0, TILE, 8));
    tile(T.BRICK, 0xbf6b3f, (x) => {
      g.lineStyle(2, 0x7f3f1f).strokeRect(x + 1, 1, TILE - 2, TILE - 2).lineBetween(x, 16, x + TILE, 16).lineBetween(x + 16, 0, x + 16, 16);
    });
    tile(T.WATER, 0x1e88e5, (x) => g.fillStyle(0x64b5f6).fillRect(x + 6, 10, 10, 2).fillRect(x + 16, 22, 10, 2));
    tile(T.SAND, 0xe6d690);
    tile(T.GRASS, 0x7cb342, (x) => g.fillStyle(0x8bc34a).fillRect(x + 6, 8, 2, 4).fillRect(x + 22, 20, 2, 4));
    tile(T.FOREST, 0x558b2f, (x) => g.fillStyle(0x2e7d32).fillCircle(x + 16, 14, 11).fillStyle(0x5d4037).fillRect(x + 14, 24, 4, 8));
    tile(T.MOUNTAIN, 0x8d8d8d, (x) => g.fillStyle(0x616161).fillTriangle(x + 2, 30, x + 16, 3, x + 30, 30).fillStyle(0xffffff).fillTriangle(x + 12, 11, x + 16, 3, x + 20, 11));
    tile(T.WALL, 0x455a64, (x) => g.lineStyle(1, 0x263238).strokeRect(x + 0.5, 0.5, TILE - 1, TILE - 1));
    tile(T.FLOOR, 0x263238, (x) => g.fillStyle(0x37474f).fillRect(x + 15, 15, 2, 2));
    tile(T.STAIRS, 0x263238, (x) => {
      g.fillStyle(0xffd54f);
      for (let k = 0; k < 4; k++) g.fillRect(x + 6 + k * 5, 8 + k * 5, 20 - k * 5, 4);
    });
  });
}
