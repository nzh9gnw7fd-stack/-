const KEY = 'game.highScore';

/** ハイスコアを読み込む（保存できない環境では 0） */
export function loadHighScore(storage: Pick<Storage, 'getItem'> | undefined = safeStorage()): number {
  try {
    const n = Number(storage?.getItem(KEY));
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
  } catch {
    return 0;
  }
}

/** スコアが記録を超えていれば保存し、更新したかどうかを返す */
export function saveHighScore(score: number, storage: Pick<Storage, 'getItem' | 'setItem'> | undefined = safeStorage()): boolean {
  if (score <= loadHighScore(storage)) return false;
  try {
    storage?.setItem(KEY, String(score));
  } catch {
    // プライベートモード等で保存できなくてもゲームは続行する
  }
  return true;
}

function safeStorage(): Storage | undefined {
  try {
    return globalThis.localStorage;
  } catch {
    return undefined;
  }
}
