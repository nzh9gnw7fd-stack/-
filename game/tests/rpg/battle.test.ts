import { describe, expect, it } from 'vitest';
import { mulberry32 } from '../../src/core/random';
import { ENCOUNTERS, SKILLS, expForLevel } from '../../src/rpg/data';
import { Battle, rollEncounter, type Action } from '../../src/rpg/battle';
import { addEquip, equip, gainExp, newGame, type GameState } from '../../src/rpg/state';

/** テスト用のそこそこ賢い AI（回復が必要なら回復、それ以外は一番強い攻撃） */
function autoActions(b: Battle): Action[] {
  const target = b.alive('enemy').sort((x, y) => x.hp - y.hp)[0].key;
  return b.alive('party').map((f): Action => {
    const hurt = b.alive('party').find((p) => p.hp < p.stats.maxHp * 0.4);
    const dead = b.party.find((p) => p.hp <= 0);
    if (f.key === 'sera') {
      if (dead && f.mp >= SKILLS.revive.mp && f.member!.level >= 5) return { actor: f.key, kind: 'skill', skill: 'revive', target: dead.key };
      if (hurt && f.mp >= 3) return { actor: f.key, kind: 'skill', skill: 'heal', target: hurt.key };
    }
    if (f.key === 'mia' && f.mp >= 9 && f.member!.level >= 7) return { actor: f.key, kind: 'skill', skill: 'thunder', target };
    if (f.key === 'mia' && f.mp >= 3) return { actor: f.key, kind: 'skill', skill: 'fire', target };
    if (f.key === 'allen' && f.mp >= 3 && f.member!.level >= 3) return { actor: f.key, kind: 'skill', skill: 'slash', target };
    return { actor: f.key, kind: 'attack', target };
  });
}

function fight(state: GameState, enemies: Parameters<typeof rollEncounter>[0]['enemies'][number][0][], seed: number, canFlee = true) {
  const b = new Battle(state, enemies, { canFlee }, mulberry32(seed));
  for (let i = 0; i < 100 && b.result === 'ongoing'; i++) b.runTurn(autoActions(b));
  return b;
}

function partyAt(level: number, gear: boolean): GameState {
  const s = newGame();
  for (const m of s.party) gainExp(m, expForLevel(level));
  if (gear) {
    for (const e of ['steelSword', 'magicStaff', 'chain', 'silkRobe', 'chain'] as const) addEquip(s, e);
    equip(s, s.party[0], 'weapon', 'steelSword');
    equip(s, s.party[0], 'armor', 'chain');
    equip(s, s.party[1], 'weapon', 'magicStaff');
    equip(s, s.party[1], 'armor', 'silkRobe');
    equip(s, s.party[2], 'armor', 'chain');
  }
  return s;
}

describe('バトル', () => {
  it('スライム1匹ならレベル1でも勝てる', () => {
    const s = newGame();
    const b = fight(s, ['slime'], 1);
    expect(b.result).toBe('win');
    expect(b.rewards().exp).toBe(4);
  });
  it('同じ敵には A, B と名前が付く', () => {
    const b = new Battle(newGame(), ['slime', 'slime', 'bat']);
    expect(b.enemies.map((e) => e.name)).toEqual(['スライムA', 'スライムB', 'おおこうもり']);
  });
  it('倒れた敵を狙った攻撃は別の敵に向かう', () => {
    const s = newGame();
    const b = new Battle(s, ['slime', 'slime'], { canFlee: true }, mulberry32(3));
    b.get('e0').hp = 0;
    const ev = b.runTurn([{ actor: 'allen', kind: 'attack', target: 'e0' }]);
    const hits = ev.filter((e) => e.t === 'damage' && e.target.startsWith('e'));
    expect(hits.every((h) => h.t === 'damage' && h.target === 'e1')).toBe(true);
  });
  it('ボスからは逃げられない', () => {
    const b = new Battle(newGame(), ['golem'], { canFlee: false });
    const ev = b.runTurn([{ actor: 'allen', kind: 'flee' }]);
    expect(ev.some((e) => e.t === 'msg' && e.text === 'にげられない！')).toBe(true);
    expect(b.result).not.toBe('fled');
  });
  it('道具を使うと持ち物から減る', () => {
    const s = newGame();
    s.party[0].hp = 1;
    const b = new Battle(s, ['slime'], { canFlee: true }, mulberry32(1));
    b.runTurn([{ actor: 'sera', kind: 'item', item: 'herb', target: 'allen' }]);
    expect(s.items.herb).toBe(2);
  });
  it('commit で HP がゲームの状態に戻る', () => {
    const s = newGame();
    const b = new Battle(s, ['slime']);
    b.get('allen').hp = 3;
    b.commit();
    expect(s.party[0].hp).toBe(3);
  });
  it('出現テーブルから 1〜maxGroup 体選ばれる', () => {
    for (let seed = 1; seed < 50; seed++) {
      const g = rollEncounter(ENCOUNTERS.field, mulberry32(seed));
      expect(g.length).toBeGreaterThanOrEqual(1);
      expect(g.length).toBeLessThanOrEqual(3);
    }
  });
});

describe('バランス（ボス戦のシミュレーション）', () => {
  const winRate = (level: number, gear: boolean) => {
    let wins = 0;
    for (let seed = 1; seed <= 40; seed++) {
      const s = partyAt(level, gear);
      for (const m of s.party) {
        // HP/MP を最大値にそろえる
        const b0 = new Battle(s, ['slime']);
        const f = b0.get(m.id);
        m.hp = f.stats.maxHp;
        m.mp = f.stats.maxMp;
      }
      s.items = { herb: 5, potion: 2, phoenix: 1 };
      if (fight(s, ['golem'], seed, false).result === 'win') wins++;
    }
    return wins / 40;
  };
  it('レベル3・初期装備ではほぼ勝てない', () => {
    expect(winRate(3, false)).toBeLessThan(0.1);
  });
  it('レベル8・良い装備ならだいたい勝てる', () => {
    expect(winRate(8, true)).toBeGreaterThan(0.6);
  });
});
