import { describe, expect, it } from 'vitest';
import { StateMachine } from '../src/core/stateMachine';

describe('StateMachine', () => {
  it('enter / update / exit を順に呼ぶ', () => {
    const log: string[] = [];
    const fsm = new StateMachine({}, {
      a: { enter: () => log.push('enter a'), update: () => log.push('update a'), exit: () => log.push('exit a') },
      b: { enter: (_c, data) => log.push(`enter b ${data}`) },
    });
    fsm.go('a');
    fsm.update(16);
    fsm.go('b', 'x');
    expect(log).toEqual(['enter a', 'update a', 'exit a', 'enter b x']);
    expect(fsm.current).toBe('b');
  });
  it('状態ごとの経過時間を数える', () => {
    const fsm = new StateMachine({}, { a: {}, b: {} });
    fsm.go('a');
    fsm.update(100);
    fsm.update(50);
    expect(fsm.timeInState).toBe(150);
    fsm.go('b');
    expect(fsm.timeInState).toBe(0);
  });
});
