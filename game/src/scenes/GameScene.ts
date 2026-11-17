import Phaser from 'phaser';
import { GAME_DURATION_SEC, GAME_HEIGHT, GAME_WIDTH, PLAYER_SPEED } from '../config';
import { inputToVelocity } from '../logic/movement';

/** サンプルのゲーム本体: プレイヤーを動かしてコインを集める */
export class GameScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Image;
  private coin!: Phaser.Physics.Arcade.Image;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd!: Record<'W' | 'A' | 'S' | 'D', Phaser.Input.Keyboard.Key>;
  private score = 0;
  private timeLeft = GAME_DURATION_SEC;
  private scoreText!: Phaser.GameObjects.Text;
  private timeText!: Phaser.GameObjects.Text;

  constructor() {
    super('Game');
  }

  create(): void {
    this.score = 0;
    this.timeLeft = GAME_DURATION_SEC;

    this.player = this.physics.add.image(GAME_WIDTH / 2, GAME_HEIGHT / 2, 'player').setCollideWorldBounds(true);
    this.coin = this.physics.add.image(0, 0, 'coin');
    this.moveCoin();
    this.physics.add.overlap(this.player, this.coin, () => this.collectCoin());

    const kb = this.input.keyboard!;
    this.cursors = kb.createCursorKeys();
    this.wasd = kb.addKeys('W,A,S,D') as typeof this.wasd;

    const style = { fontSize: '24px', color: '#ffffff' };
    this.scoreText = this.add.text(16, 16, '', style);
    this.timeText = this.add.text(GAME_WIDTH - 16, 16, '', style).setOrigin(1, 0);
    this.updateHud();

    this.time.addEvent({
      delay: 1000,
      repeat: GAME_DURATION_SEC - 1,
      callback: () => {
        this.timeLeft--;
        this.updateHud();
        if (this.timeLeft <= 0) this.scene.start('Result', { score: this.score });
      },
    });
  }

  update(): void {
    const { vx, vy } = inputToVelocity(
      {
        left: this.cursors.left.isDown || this.wasd.A.isDown,
        right: this.cursors.right.isDown || this.wasd.D.isDown,
        up: this.cursors.up.isDown || this.wasd.W.isDown,
        down: this.cursors.down.isDown || this.wasd.S.isDown,
      },
      PLAYER_SPEED,
    );
    this.player.setVelocity(vx, vy);
  }

  private collectCoin(): void {
    this.score++;
    this.updateHud();
    this.cameras.main.flash(80, 255, 213, 79);
    this.moveCoin();
  }

  private moveCoin(): void {
    const margin = 40;
    this.coin.setPosition(
      Phaser.Math.Between(margin, GAME_WIDTH - margin),
      Phaser.Math.Between(margin + 40, GAME_HEIGHT - margin),
    );
  }

  private updateHud(): void {
    this.scoreText.setText(`SCORE: ${this.score}`);
    this.timeText.setText(`TIME: ${this.timeLeft}`);
  }
}
