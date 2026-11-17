import { describe, expect, it } from 'vitest';
import { loadHighScore, saveHighScore } from '../src/logic/highScore';

function memoryStorage() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
}

describe('highScore', () => {
  it('初期値は 0', () => {
    expect(loadHighScore(memoryStorage())).toBe(0);
  });
  it('記録更新時だけ保存する', () => {
    const s = memoryStorage();
    expect(saveHighScore(5, s)).toBe(true);
    expect(saveHighScore(3, s)).toBe(false);
    expect(loadHighScore(s)).toBe(5);
  });
  it('ストレージが無くても落ちない', () => {
    expect(loadHighScore(undefined)).toBe(0);
    expect(saveHighScore(1, undefined)).toBe(true);
  });
});
