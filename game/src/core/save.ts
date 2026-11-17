/**
 * セーブデータ（ブラウザの localStorage に JSON で保存）。
 * 保存できない環境（プライベートモード等）でも例外を出さずに動く。
 *
 *   saveData('rpg', { level: 3, items: ['sword'] });
 *   const data = loadData('rpg', { level: 1, items: [] });
 */
export type KeyValueStorage = Pick<Storage, 'getItem' | 'setItem'>;

const PREFIX = 'game.';

function safeStorage(): KeyValueStorage | undefined {
  try {
    return globalThis.localStorage;
  } catch {
    return undefined;
  }
}

export function loadData<T>(key: string, fallback: T, storage: KeyValueStorage | undefined = safeStorage()): T {
  try {
    const raw = storage?.getItem(PREFIX + key);
    return raw == null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function saveData(key: string, value: unknown, storage: KeyValueStorage | undefined = safeStorage()): boolean {
  try {
    if (!storage) return false;
    storage.setItem(PREFIX + key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function loadHighScore(game: string, storage: KeyValueStorage | undefined = safeStorage()): number {
  const n = loadData<unknown>(`${game}.highScore`, 0, storage);
  return typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}

/** 記録を更新したら保存して true を返す */
export function saveHighScore(game: string, score: number, storage: KeyValueStorage | undefined = safeStorage()): boolean {
  if (score <= loadHighScore(game, storage)) return false;
  saveData(`${game}.highScore`, score, storage);
  return true;
}
