import type Phaser from 'phaser';

export const RT = 32; // タイルの大きさ

/** RPG 用タイルセットの番号 */
export const RTile = {
  GRASS: 0, PATH: 1, TREE: 2, MOUNTAIN: 3, WATER: 4, WALL: 5, ROOF: 6, FLOOR: 7, DOOR: 8, COUNTER: 9,
  CAVE_FLOOR: 10, CAVE_WALL: 11, CAVE: 12, VILLAGE: 13, WELL: 14, FLOWER: 15, BRIDGE: 16, STAIRS: 17, SPRING: 18,
} as const;
const TILE_COUNT = 19;

type G = Phaser.GameObjects.Graphics;

/** 画像ファイルなしで遊べるよう、タイル・キャラ・敵の絵を図形で描く */
export function createRpgTextures(scene: Phaser.Scene): void {
  const make = (key: string, w: number, h: number, draw: (g: G) => void) => {
    if (scene.textures.exists(key)) return;
    const g = scene.make.graphics({ x: 0, y: 0 }, false);
    draw(g);
    g.generateTexture(key, w, h);
    g.destroy();
  };

  make('rpg-tiles', RT * TILE_COUNT, RT, (g) => {
    const at = (i: number, base: number | null, draw?: (x: number) => void) => {
      if (base !== null) g.fillStyle(base).fillRect(i * RT, 0, RT, RT);
      draw?.(i * RT);
    };
    const grass = (x: number) => { g.fillStyle(0x6fbf4a).fillRect(x, 0, RT, RT); g.fillStyle(0x86d05e).fillRect(x + 5, 6, 2, 3).fillRect(x + 20, 18, 2, 3).fillRect(x + 12, 26, 2, 3); };
    at(RTile.GRASS, null, grass);
    at(RTile.PATH, 0xd9c08a, (x) => g.fillStyle(0xc9ad74).fillRect(x + 6, 8, 3, 2).fillRect(x + 22, 20, 3, 2));
    at(RTile.TREE, null, (x) => { grass(x); g.fillStyle(0x6d4c41).fillRect(x + 13, 20, 6, 10); g.fillStyle(0x2e7d32).fillCircle(x + 16, 13, 12); g.fillStyle(0x43a047).fillCircle(x + 12, 10, 6); });
    at(RTile.MOUNTAIN, null, (x) => { grass(x); g.fillStyle(0x8d7b68).fillTriangle(x, 32, x + 16, 2, x + 32, 32); g.fillStyle(0x6d5d4b).fillTriangle(x + 16, 2, x + 32, 32, x + 20, 32); g.fillStyle(0xffffff).fillTriangle(x + 11, 12, x + 16, 2, x + 21, 12); });
    at(RTile.WATER, 0x2f7fd6, (x) => g.fillStyle(0x6fb3f0).fillRect(x + 4, 8, 10, 2).fillRect(x + 18, 20, 10, 2));
    at(RTile.WALL, 0xb0a08a, (x) => { g.lineStyle(2, 0x8a7a64); for (let r = 0; r < 4; r++) g.lineBetween(x, r * 8, x + RT, r * 8).lineBetween(x + (r % 2) * 16 + 8, r * 8, x + (r % 2) * 16 + 8, r * 8 + 8); });
    at(RTile.ROOF, 0xb5473a, (x) => { g.fillStyle(0x93362b); for (let r = 0; r < 4; r++) g.fillRect(x, r * 8 + 6, RT, 2); });
    at(RTile.FLOOR, 0xc49a6c, (x) => { g.lineStyle(1, 0xa47a4c); for (let r = 1; r < 4; r++) g.lineBetween(x, r * 8, x + RT, r * 8); });
    at(RTile.DOOR, 0xc49a6c, (x) => g.fillStyle(0x6d4c41).fillRect(x + 6, 0, 20, 32).fillStyle(0xffd54f).fillCircle(x + 21, 17, 2));
    at(RTile.COUNTER, 0xc49a6c, (x) => g.fillStyle(0x8d5a3a).fillRect(x, 6, RT, 22).fillStyle(0xa8714a).fillRect(x, 6, RT, 5));
    at(RTile.CAVE_FLOOR, 0x4a4250, (x) => g.fillStyle(0x5a5262).fillRect(x + 8, 10, 3, 3).fillRect(x + 22, 22, 2, 2));
    at(RTile.CAVE_WALL, 0x231e2a, (x) => g.fillStyle(0x342d3d).fillRect(x + 2, 2, 12, 10).fillRect(x + 16, 16, 14, 12));
    at(RTile.CAVE, null, (x) => { grass(x); g.fillStyle(0x8d7b68).fillTriangle(x, 32, x + 16, 0, x + 32, 32); g.fillStyle(0x1a1520).fillEllipse(x + 16, 26, 16, 16); });
    at(RTile.VILLAGE, null, (x) => { grass(x); g.fillStyle(0xb5473a).fillTriangle(x + 2, 16, x + 11, 6, x + 20, 16).fillTriangle(x + 13, 20, x + 22, 10, x + 31, 20); g.fillStyle(0xeee0c0).fillRect(x + 4, 16, 14, 10).fillRect(x + 15, 20, 14, 10); });
    at(RTile.WELL, null, (x) => { grass(x); g.fillStyle(0x9e9e9e).fillCircle(x + 16, 16, 13); g.fillStyle(0x5d4037).fillCircle(x + 16, 16, 8); });
    at(RTile.FLOWER, null, (x) => { grass(x); for (const [fx, fy, c] of [[8, 8, 0xff8a80], [22, 12, 0xfff176], [12, 22, 0xce93d8], [25, 25, 0xff8a80]] as const) g.fillStyle(c).fillCircle(x + fx, fy, 3); });
    at(RTile.BRIDGE, 0x2f7fd6, (x) => { g.fillStyle(0xa1734a).fillRect(x, 4, RT, 24); g.lineStyle(2, 0x7a5232); for (let i = 0; i < 4; i++) g.lineBetween(x + i * 8, 4, x + i * 8, 28); });
    at(RTile.STAIRS, 0x4a4250, (x) => { for (let i = 0; i < 4; i++) g.fillStyle(0x8a8296 - i * 0x111111).fillRect(x + 4, 4 + i * 7, 24, 6); });
    at(RTile.SPRING, 0x4a4250, (x) => { g.fillStyle(0x4dd0e1).fillCircle(x + 16, 16, 13); g.fillStyle(0xb2ebf2).fillCircle(x + 12, 12, 4); });
  });

  // 人物（下・上・横向き）
  const person = (key: string, body: number, hair: number, opts: { beard?: boolean; hat?: number } = {}) => {
    for (const dir of ['down', 'up', 'side'] as const) {
      make(`${key}-${dir}`, 32, 32, (g) => {
        g.fillStyle(0x000000, 0.2).fillEllipse(16, 30, 20, 5);
        g.fillStyle(body).fillRoundedRect(8, 15, 16, 14, 4);
        g.fillStyle(0xffe0bd).fillCircle(16, 11, 8);
        g.fillStyle(hair);
        if (dir === 'up') g.fillCircle(16, 10, 8.5);
        else g.fillRect(8, 3, 16, 5).fillRect(8, 3, 3, 9).fillRect(21, 3, 3, dir === 'side' ? 5 : 9);
        if (dir !== 'up') {
          g.fillStyle(0x222222);
          if (dir === 'down') g.fillRect(12, 11, 2, 3).fillRect(18, 11, 2, 3);
          else g.fillRect(19, 11, 2, 3);
          if (opts.beard) g.fillStyle(0xffffff).fillTriangle(10, 14, 22, 14, 16, 24);
        }
        if (opts.hat !== undefined) g.fillStyle(opts.hat).fillTriangle(6, 6, 26, 6, 16, -6).fillRect(5, 4, 22, 3);
      });
    }
  };
  person('hero', 0x42a5f5, 0x6d4c41);
  person('elder', 0x8e7cc3, 0xeeeeee, { beard: true });
  person('merchant', 0xffa726, 0x4e342e);
  person('innkeeper', 0xec407a, 0x795548);
  person('villager', 0x8bc34a, 0x3e2723);
  person('girl', 0xffee58, 0xff7043);
  person('guard', 0x78909c, 0x37474f, { hat: 0x546e7a });

  make('chest', 32, 32, (g) => {
    g.fillStyle(0x8d5a2b).fillRect(4, 10, 24, 18);
    g.fillStyle(0xa86b33).fillRect(4, 8, 24, 7);
    g.fillStyle(0xffd54f).fillRect(4, 14, 24, 2).fillRect(14, 12, 4, 6);
  });
  make('chest-open', 32, 32, (g) => {
    g.fillStyle(0x5d3a1a).fillRect(4, 10, 24, 6);
    g.fillStyle(0x8d5a2b).fillRect(4, 14, 24, 14);
    g.fillStyle(0xffd54f).fillRect(4, 14, 24, 2);
  });
  make('cursor', 16, 16, (g) => g.fillStyle(0xffffff).fillTriangle(0, 0, 14, 8, 0, 16));
  make('target', 24, 16, (g) => g.fillStyle(0xffeb3b).fillTriangle(0, 0, 24, 0, 12, 16));

  // ---- 敵 ----
  const eyes = (g: G, x1: number, x2: number, y: number, r = 5, color = 0xffffff) => {
    g.fillStyle(color).fillCircle(x1, y, r).fillCircle(x2, y, r);
    g.fillStyle(0x111111).fillCircle(x1 + 1, y + 1, r / 2).fillCircle(x2 + 1, y + 1, r / 2);
  };
  make('e-slime', 96, 96, (g) => {
    g.fillStyle(0x000000, 0.25).fillEllipse(48, 90, 70, 10);
    g.fillStyle(0x4fc3f7).fillEllipse(48, 64, 76, 50).fillTriangle(30, 50, 48, 18, 66, 50);
    g.fillStyle(0xb3e5fc).fillEllipse(34, 52, 14, 10);
    eyes(g, 38, 58, 64);
    g.lineStyle(3, 0x0d47a1).beginPath().arc(48, 72, 8, 0.2, Math.PI - 0.2).strokePath();
  });
  make('e-bat', 120, 80, (g) => {
    g.fillStyle(0x5e35b1).fillTriangle(60, 40, 4, 10, 20, 60).fillTriangle(60, 40, 116, 10, 100, 60);
    g.fillStyle(0x4527a0).fillTriangle(20, 60, 30, 40, 40, 62).fillTriangle(100, 60, 90, 40, 80, 62);
    g.fillStyle(0x311b92).fillCircle(60, 42, 18).fillTriangle(46, 30, 50, 12, 56, 28).fillTriangle(74, 30, 70, 12, 64, 28);
    eyes(g, 53, 67, 40, 4, 0xffeb3b);
    g.fillStyle(0xffffff).fillTriangle(54, 52, 58, 52, 56, 58).fillTriangle(62, 52, 66, 52, 64, 58);
  });
  make('e-boar', 120, 96, (g) => {
    g.fillStyle(0x000000, 0.25).fillEllipse(60, 90, 90, 10);
    g.fillStyle(0x6d4c41).fillEllipse(66, 56, 90, 54);
    g.fillStyle(0x4e342e).fillRect(30, 70, 12, 18).fillRect(84, 70, 12, 18).fillTriangle(60, 30, 80, 20, 100, 34);
    g.fillStyle(0x8d6e63).fillEllipse(26, 58, 40, 36);
    g.fillStyle(0xd7ccc8).fillEllipse(12, 64, 14, 12);
    g.fillStyle(0xffffff).fillTriangle(16, 70, 22, 70, 10, 84);
    eyes(g, 26, 40, 50, 4, 0xffcdd2);
  });
  make('e-goblin', 96, 120, (g) => {
    g.fillStyle(0x000000, 0.25).fillEllipse(48, 114, 60, 10);
    g.fillStyle(0x558b2f).fillRoundedRect(26, 54, 44, 50, 10);
    g.fillStyle(0x795548).fillRect(26, 80, 44, 12);
    g.fillStyle(0x7cb342).fillCircle(48, 38, 24).fillTriangle(24, 34, 4, 22, 28, 46).fillTriangle(72, 34, 92, 22, 68, 46);
    eyes(g, 39, 57, 36, 5, 0xfff176);
    g.fillStyle(0xffffff).fillTriangle(40, 50, 46, 50, 43, 56).fillTriangle(50, 50, 56, 50, 53, 56);
    g.fillStyle(0x8d6e63).fillRect(74, 50, 8, 52);
    g.fillStyle(0x5d4037).fillCircle(78, 48, 10);
  });
  make('e-skeleton', 96, 128, (g) => {
    g.fillStyle(0x000000, 0.25).fillEllipse(48, 122, 60, 10);
    g.fillStyle(0xeeeeee);
    g.fillCircle(48, 28, 20).fillRect(44, 46, 8, 50);
    for (let i = 0; i < 4; i++) g.fillRect(30, 56 + i * 9, 36, 4);
    g.fillRect(30, 96, 6, 24).fillRect(60, 96, 6, 24).fillRect(20, 52, 6, 36).fillRect(70, 52, 6, 36);
    g.fillStyle(0x222222).fillCircle(40, 26, 6).fillCircle(56, 26, 6).fillRect(40, 38, 16, 4);
    g.fillStyle(0xff1744).fillCircle(40, 26, 2).fillCircle(56, 26, 2);
    g.fillStyle(0x90a4ae).fillRect(80, 30, 5, 70).fillRect(72, 90, 21, 5);
  });
  make('e-mage', 100, 128, (g) => {
    g.fillStyle(0x000000, 0.25).fillEllipse(50, 122, 60, 10);
    g.fillStyle(0x4a148c).fillTriangle(50, 30, 14, 120, 86, 120);
    g.fillStyle(0x6a1b9a).fillTriangle(50, 0, 26, 40, 74, 40);
    g.fillStyle(0x12001f).fillCircle(50, 44, 15);
    eyes(g, 44, 56, 44, 3, 0xff4081);
    g.fillStyle(0x795548).fillRect(84, 30, 5, 90);
    g.fillStyle(0xe040fb).fillCircle(86, 26, 9);
    g.fillStyle(0xf3e5f5, 0.6).fillCircle(83, 23, 3);
  });
  make('e-golem', 240, 240, (g) => {
    g.fillStyle(0x000000, 0.3).fillEllipse(120, 230, 200, 18);
    g.fillStyle(0x6d6259);
    g.fillRoundedRect(50, 70, 140, 120, 20);
    g.fillRoundedRect(10, 80, 50, 110, 18).fillRoundedRect(180, 80, 50, 110, 18);
    g.fillRoundedRect(70, 180, 40, 50, 10).fillRoundedRect(130, 180, 40, 50, 10);
    g.fillStyle(0x857869).fillRoundedRect(80, 14, 80, 70, 16);
    g.fillStyle(0x4e453e);
    g.fillRect(60, 100, 50, 8).fillRect(130, 140, 50, 8).fillRect(90, 160, 20, 6);
    g.fillStyle(0x66bb6a).fillCircle(70, 80, 8).fillCircle(170, 120, 6).fillCircle(30, 90, 5);
    g.fillStyle(0xff6d00).fillCircle(104, 46, 9).fillCircle(136, 46, 9);
    g.fillStyle(0xffff8d).fillCircle(104, 46, 4).fillCircle(136, 46, 4);
    g.fillStyle(0x2b2520).fillRect(100, 66, 40, 8);
  });
}
