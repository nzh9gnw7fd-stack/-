import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from './config';
import { BootScene } from './scenes/BootScene';
import { MenuScene } from './scenes/MenuScene';
import { CoinDashScene } from './samples/CoinDashScene';
import { PlatformerScene } from './samples/PlatformerScene';
import { ShooterScene } from './samples/ShooterScene';
import { Match3Scene } from './samples/Match3Scene';
import { FieldScene } from './samples/FieldScene';
import { RoguelikeScene } from './samples/RoguelikeScene';
import { PhysicsScene } from './samples/PhysicsScene';
import { NovelScene } from './samples/NovelScene';

const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: GAME_WIDTH,
  height: GAME_HEIGHT,
  backgroundColor: '#1d2033',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  input: { gamepad: true },
  physics: { default: 'arcade', arcade: { debug: false } },
  scene: [BootScene, MenuScene, CoinDashScene, PlatformerScene, ShooterScene, Match3Scene, FieldScene, RoguelikeScene, PhysicsScene, NovelScene],
});

// 開発中はブラウザのコンソールから game でゲームの中身を見られる
//   例: game.scene.getScene('Shooter').score
if (import.meta.env.DEV) {
  (window as unknown as { game: Phaser.Game }).game = game;
}
