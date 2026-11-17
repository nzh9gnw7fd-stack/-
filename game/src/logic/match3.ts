/**
 * マッチ3パズルの盤面ロジック（描画とは独立、テスト可能）。
 * board[row][col] に色番号（0〜kinds-1）、空きは -1。
 */
export type Board = number[][];
export interface Cell { r: number; c: number }
export interface FallMove { from: Cell | null; to: Cell; kind: number; /** 新しく出てきた場合、上から何個目か */ spawnIndex?: number }

export function createBoard(rows: number, cols: number, kinds: number, rng: () => number = Math.random): Board {
  for (;;) {
    const b: Board = [];
    for (let r = 0; r < rows; r++) {
      b.push([]);
      for (let c = 0; c < cols; c++) {
        let k: number;
        do {
          k = Math.floor(rng() * kinds);
        } while ((c >= 2 && b[r][c - 1] === k && b[r][c - 2] === k) || (r >= 2 && b[r - 1][c] === k && b[r - 2][c] === k));
        b[r].push(k);
      }
    }
    if (hasPossibleMove(b)) return b;
  }
}

export function cloneBoard(b: Board): Board {
  return b.map((row) => row.slice());
}

export function isAdjacent(a: Cell, b: Cell): boolean {
  return Math.abs(a.r - b.r) + Math.abs(a.c - b.c) === 1;
}

export function swap(b: Board, a: Cell, c: Cell): Board {
  const n = cloneBoard(b);
  [n[a.r][a.c], n[c.r][c.c]] = [n[c.r][c.c], n[a.r][a.c]];
  return n;
}

/** 縦横に 3 つ以上並んだマスをすべて返す（重複なし） */
export function findMatches(b: Board): Cell[] {
  const rows = b.length;
  const cols = b[0]?.length ?? 0;
  const hit = new Set<string>();
  const scan = (len: number, other: number, get: (i: number, j: number) => number, key: (i: number, j: number) => string) => {
    for (let j = 0; j < other; j++) {
      let start = 0;
      for (let i = 1; i <= len; i++) {
        if (i < len && get(i, j) === get(start, j) && get(start, j) !== -1) continue;
        if (i - start >= 3 && get(start, j) !== -1) for (let k = start; k < i; k++) hit.add(key(k, j));
        start = i;
      }
    }
  };
  scan(cols, rows, (i, j) => b[j][i], (i, j) => `${j},${i}`);
  scan(rows, cols, (i, j) => b[i][j], (i, j) => `${i},${j}`);
  return [...hit].map((s) => {
    const [r, c] = s.split(',').map(Number);
    return { r, c };
  });
}

/** 消えたマスに上から落とし、空いたところに新しい色を補充する */
export function collapse(b: Board, kinds: number, rng: () => number = Math.random): { board: Board; moves: FallMove[] } {
  const n = cloneBoard(b);
  const rows = n.length;
  const moves: FallMove[] = [];
  for (let c = 0; c < (n[0]?.length ?? 0); c++) {
    let write = rows - 1;
    for (let r = rows - 1; r >= 0; r--) {
      if (n[r][c] === -1) continue;
      if (r !== write) {
        moves.push({ from: { r, c }, to: { r: write, c }, kind: n[r][c] });
        n[write][c] = n[r][c];
        n[r][c] = -1;
      }
      write--;
    }
    for (let r = write, i = 0; r >= 0; r--, i++) {
      n[r][c] = Math.floor(rng() * kinds);
      moves.push({ from: null, to: { r, c }, kind: n[r][c], spawnIndex: i });
    }
  }
  return { board: n, moves };
}

export function hasPossibleMove(b: Board): boolean {
  for (let r = 0; r < b.length; r++) {
    for (let c = 0; c < b[r].length; c++) {
      for (const [dr, dc] of [[0, 1], [1, 0]]) {
        const o = { r: r + dr, c: c + dc };
        if (o.r >= b.length || o.c >= b[r].length) continue;
        if (findMatches(swap(b, { r, c }, o)).length > 0) return true;
      }
    }
  }
  return false;
}
