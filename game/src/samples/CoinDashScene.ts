import Phaser from 'phaser';
import { GAME_HEIGHT, GAME_WIDTH } from '../config';
import { GameInput } from '../core/input';
import { loadHighScore, saveHighScore } from '../core/save';
import { sfx } from '../core/sfx';
import { StateMachine } from '../core/stateMachine';
import { addSampleChrome, text } from '../core/ui';

const DURATION = 30_000;
const SPEED = 260;

/** トップダウンのミニゲーム。StateMachine で「待機→プレイ→結果」を切り替える例。 */
export class CoinDashScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Image;
  private coin!: Phaser.Physics.Arcade.Image;
  private controls!: GameInput;
  private hud!: Phaser.GameObjects.Text;
  private message!: Phaser.GameObjects.Text;
  private score = 0;
  private timeLeft = DURATION;
  private fsm!: StateMachine<'ready' | 'play' | 'result', CoinDashScene>;

  constructor() {
    super('CoinDash');
  }

  create(): void {
    this.score = 0;
    this.timeLeft = DURATION;
    this.controls = new GameInput(this);
    this.player = this.physics.add.image(GAME_WIDTH / 2, GAME_HEIGHT / 2, 'player').setCollideWorldBounds(true);
    this.coin = this.physics.add.image(0, 0, 'coin');
    this.moveCoin();
    this.physics.add.overlap(this.player, this.coin, () => {
      if (this.fsm.current !== 'play') return;
      this.score++;
      sfx.coin();
      this.cameras.main.flash(80, 255, 213, 79);
      this.moveCoin();
    });
    this.hud = text(this, 16, 16, '', 22);
    this.message = text(this, GAME_WIDTH / 2, GAME_HEIGHT / 2 - 80, '', 28, '#ffd54f').setOrigin(0.5).setAlign('center');
    addSampleChrome(this, '移動: 矢印/WASD  決定: Space');

    this.fsm = new StateMachine(this, {
      ready: {
        enter: (s) => s.message.setText(`30秒でコインを集めよう\nSPACE でスタート\n\nハイスコア: ${loadHighScore('coindash')}`),
        update: (s) => { if (s.controls.actionPressed) s.fsm.go('play'); },
      },
      play: {
        enter: (s) => s.message.setText(''),
        update: (s, dt) => {
          const { x, y } = s.controls.axis;
          s.player.setVelocity(x * SPEED, y * SPEED);
          s.timeLeft = Math.max(0, s.timeLeft - dt);
          if (s.timeLeft === 0) s.fsm.go('result');
        },
      },
      result: {
        enter: (s) => {
          s.player.setVelocity(0, 0);
          sfx.powerup();
          const best = saveHighScore('coindash', s.score);
          s.message.setText(`TIME UP!  SCORE: ${s.score}${best ? '\nNEW RECORD!' : ''}\n\nSPACE でもう一度`);
        },
        update: (s) => { if (s.fsm.timeInState > 500 && s.controls.actionPressed) s.scene.restart(); },
      },
    });
    this.fsm.go('ready');
  }

  update(_time: number, dt: number): void {
    this.fsm.update(dt);
    this.hud.setText(`SCORE: ${this.score}   TIME: ${Math.ceil(this.timeLeft / 1000)}`);
  }

  private moveCoin(): void {
    this.coin.setPosition(Phaser.Math.Between(40, GAME_WIDTH - 40), Phaser.Math.Between(80, GAME_HEIGHT - 60));
  }
}
