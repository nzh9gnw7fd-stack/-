import { describe, expect, it } from 'vitest';
import { loadData, loadHighScore, saveData, saveHighScore } from '../src/core/save';

function memoryStorage() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
}

describe('save', () => {
  it('オブジェクトを保存して読み込める', () => {
    const s = memoryStorage();
    saveData('rpg', { level: 3, items: ['sword'] }, s);
    expect(loadData('rpg', { level: 1, items: [] as string[] }, s)).toEqual({ level: 3, items: ['sword'] });
  });
  it('データがなければ初期値', () => {
    expect(loadData('none', 42, memoryStorage())).toBe(42);
  });
  it('ハイスコアは更新時だけ保存', () => {
    const s = memoryStorage();
    expect(loadHighScore('g', s)).toBe(0);
    expect(saveHighScore('g', 5, s)).toBe(true);
    expect(saveHighScore('g', 3, s)).toBe(false);
    expect(loadHighScore('g', s)).toBe(5);
  });
  it('ストレージが無くても落ちない', () => {
    expect(loadHighScore('g', undefined)).toBe(0);
    expect(saveData('x', 1, undefined)).toBe(false);
  });
});
