/**
 * Phaser に依存しない純粋なロジックは src/logic/ に置くと、Vitest で簡単にテストできる。
 */
export interface DirectionInput {
  left: boolean;
  right: boolean;
  up: boolean;
  down: boolean;
}

/** 入力から速度を計算する。斜め移動でも速さが変わらないよう正規化する。 */
export function inputToVelocity(input: DirectionInput, speed: number): { vx: number; vy: number } {
  const dx = (input.right ? 1 : 0) - (input.left ? 1 : 0);
  const dy = (input.down ? 1 : 0) - (input.up ? 1 : 0);
  if (dx === 0 && dy === 0) return { vx: 0, vy: 0 };
  const len = Math.hypot(dx, dy);
  return { vx: (dx / len) * speed, vy: (dy / len) * speed };
}
