import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { createPlaceholderTextures } from '../core/textures';
import { BattleScene } from './scenes/BattleScene';
import { EndingScene } from './scenes/EndingScene';
import { MapScene } from './scenes/MapScene';
import { TitleScene } from './scenes/TitleScene';
import { game as rpg } from './state';
import { createRpgTextures } from './textures';

class BootScene extends Phaser.Scene {
  constructor() {
    super('RpgBoot');
  }

  preload(): void {
    // 自分で描いた絵を使うときは、ここで同じキー名の画像を読み込む
    //   例: this.load.image('hero-down', 'assets/rpg/hero-down.png');
  }

  create(): void {
    createPlaceholderTextures(this);
    createRpgTextures(this);
    this.scene.start('RpgTitle');
  }
}

const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: GAME_WIDTH,
  height: GAME_HEIGHT,
  backgroundColor: '#000000',
  pixelArt: true,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  input: { gamepad: true },
  scene: [BootScene, TitleScene, MapScene, BattleScene, EndingScene],
});

if (import.meta.env.DEV) {
  Object.assign(window as object, { game, rpg });
}
