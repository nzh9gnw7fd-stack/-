import { describe, expect, it } from 'vitest';
import { inputToVelocity } from '../src/logic/movement';

const none = { left: false, right: false, up: false, down: false };

describe('inputToVelocity', () => {
  it('入力なしなら停止', () => {
    expect(inputToVelocity(none, 100)).toEqual({ vx: 0, vy: 0 });
  });
  it('右入力で右へ', () => {
    expect(inputToVelocity({ ...none, right: true }, 100)).toEqual({ vx: 100, vy: 0 });
  });
  it('斜めでも速さは一定', () => {
    const { vx, vy } = inputToVelocity({ ...none, right: true, down: true }, 100);
    expect(Math.hypot(vx, vy)).toBeCloseTo(100);
  });
  it('左右同時押しは打ち消し合う', () => {
    expect(inputToVelocity({ ...none, left: true, right: true }, 100)).toEqual({ vx: 0, vy: 0 });
  });
});
