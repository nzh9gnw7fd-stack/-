import Phaser from 'phaser';
import { createPlaceholderTextures } from '../core/textures';

/**
 * 素材の読み込み。画像や音声は public/assets/ に置き、preload() で読み込む。
 *   this.load.image('player', 'assets/player.png');          // 画像（キー 'player' の仮画像を置き換え）
 *   this.load.spritesheet('hero', 'assets/hero.png', { frameWidth: 32, frameHeight: 32 }); // アニメ用
 *   this.load.audio('bgm', 'assets/bgm.mp3');                // 音楽
 *   this.load.tilemapTiledJSON('map1', 'assets/map1.json');  // Tiled で作ったマップ
 */
export class BootScene extends Phaser.Scene {
  constructor() {
    super('Boot');
  }

  preload(): void {
    const bar = this.add.rectangle(400, 300, 0, 16, 0x4fc3f7);
    this.load.on('progress', (v: number) => (bar.width = 400 * v));
  }

  create(): void {
    createPlaceholderTextures(this);
    this.scene.start('Menu');
  }
}
