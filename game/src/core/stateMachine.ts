/**
 * 小さなステートマシン。「待機→プレイ→結果」のような画面内の状態や、敵の AI（巡回→追跡→攻撃）に使える。
 *
 *   const fsm = new StateMachine(this, {
 *     idle:  { update: (ctx) => { if (見つけた) fsm.go('chase'); } },
 *     chase: { enter: (ctx) => {...}, update: (ctx, dt) => {...} },
 *   });
 *   fsm.go('idle');   // 毎フレーム fsm.update(dt)
 */
export interface State<C> {
  enter?(ctx: C, data?: unknown): void;
  update?(ctx: C, dt: number): void;
  exit?(ctx: C): void;
}

export class StateMachine<K extends string, C> {
  private _current: K | null = null;
  private elapsed = 0;

  constructor(
    private readonly ctx: C,
    private readonly states: Record<K, State<C>>,
  ) {}

  get current(): K | null {
    return this._current;
  }

  /** 現在の状態に入ってからの経過ミリ秒 */
  get timeInState(): number {
    return this.elapsed;
  }

  go(key: K, data?: unknown): void {
    if (this._current !== null) this.states[this._current].exit?.(this.ctx);
    this._current = key;
    this.elapsed = 0;
    this.states[key].enter?.(this.ctx, data);
  }

  update(dt: number): void {
    if (this._current === null) return;
    this.elapsed += dt;
    this.states[this._current].update?.(this.ctx, dt);
  }
}
