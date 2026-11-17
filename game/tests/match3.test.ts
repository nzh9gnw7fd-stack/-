import { describe, expect, it } from 'vitest';
import { mulberry32 } from '../src/core/random';
import { collapse, createBoard, findMatches, hasPossibleMove, isAdjacent, swap } from '../src/logic/match3';

describe('match3', () => {
  it('作った盤面は最初から揃っておらず、動かせる手がある', () => {
    for (let seed = 1; seed <= 20; seed++) {
      const b = createBoard(8, 8, 6, mulberry32(seed));
      expect(findMatches(b)).toEqual([]);
      expect(hasPossibleMove(b)).toBe(true);
    }
  });
  it('縦横の 3 つ並びを見つける（L字は 5 マス）', () => {
    const b = [
      [0, 0, 0],
      [1, 2, 0],
      [2, 1, 0],
    ];
    expect(findMatches(b)).toHaveLength(5);
  });
  it('-1（空き）は揃ったとみなさない', () => {
    expect(findMatches([[-1, -1, -1]])).toEqual([]);
  });
  it('隣どうしの判定', () => {
    expect(isAdjacent({ r: 0, c: 0 }, { r: 0, c: 1 })).toBe(true);
    expect(isAdjacent({ r: 0, c: 0 }, { r: 1, c: 1 })).toBe(false);
  });
  it('swap は元の盤面を変えない', () => {
    const b = [[1, 2]];
    expect(swap(b, { r: 0, c: 0 }, { r: 0, c: 1 })).toEqual([[2, 1]]);
    expect(b).toEqual([[1, 2]]);
  });
  it('collapse で上のピースが落ち、空きが補充される', () => {
    const b = [
      [3, 4],
      [-1, 5],
      [-1, 6],
    ];
    const { board, moves } = collapse(b, 6, () => 0);
    expect(board.map((r) => r[0])).toEqual([0, 0, 3]);
    expect(board.map((r) => r[1])).toEqual([4, 5, 6]);
    expect(board.flat()).not.toContain(-1);
    expect(moves.filter((m) => m.from === null)).toHaveLength(2);
  });
});
