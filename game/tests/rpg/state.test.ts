import { describe, expect, it } from 'vitest';
import { expForLevel } from '../../src/rpg/data';
import { addEquip, addItem, castFieldSkill, equip, gainExp, loadGame, newGame, saveGame, skillsOf, stats, useItemOn } from '../../src/rpg/state';

describe('RPG の状態', () => {
  it('新しいゲームは全員 HP/MP 満タン', () => {
    const s = newGame();
    for (const m of s.party) {
      expect(m.hp).toBe(stats(m).maxHp);
      expect(m.mp).toBe(stats(m).maxMp);
    }
  });
  it('経験値でレベルが上がり、技を覚える', () => {
    const s = newGame();
    const allen = s.party[0];
    expect(skillsOf(allen)).toEqual([]);
    const ups = gainExp(allen, expForLevel(3));
    expect(allen.level).toBe(3);
    expect(ups.map((u) => u.level)).toEqual([2, 3]);
    expect(ups[1].learned).toEqual(['slash']);
  });
  it('装備で能力が変わり、外した装備は持ち物に戻る', () => {
    const s = newGame();
    const allen = s.party[0];
    const before = stats(allen).atk;
    addEquip(s, 'ironSword');
    expect(equip(s, allen, 'weapon', 'ironSword')).toBe(true);
    expect(stats(allen).atk).toBe(before - 3 + 9);
    expect(s.equips.woodSword).toBe(1);
    expect(s.equips.ironSword).toBeUndefined();
  });
  it('装備できないキャラには装備できない', () => {
    const s = newGame();
    addEquip(s, 'ironSword');
    expect(equip(s, s.party[1], 'weapon', 'ironSword')).toBe(false);
  });
  it('やくそうで回復、満タンなら使わない', () => {
    const s = newGame();
    const m = s.party[0];
    expect(useItemOn(s, 'herb', m)).toBeNull();
    m.hp = 1;
    expect(useItemOn(s, 'herb', m)).not.toBeNull();
    expect(m.hp).toBe(Math.min(stats(m).maxHp, 41));
    expect(s.items.herb).toBe(2);
  });
  it('ふっかつそうは倒れた仲間にだけ効く', () => {
    const s = newGame();
    addItem(s, 'phoenix');
    const m = s.party[1];
    expect(useItemOn(s, 'phoenix', m)).toBeNull();
    m.hp = 0;
    expect(useItemOn(s, 'phoenix', m)).not.toBeNull();
    expect(m.hp).toBeGreaterThan(0);
  });
  it('フィールドでヒールを使うと MP が減る', () => {
    const s = newGame();
    const [allen, , sera] = s.party;
    allen.hp = 5;
    expect(castFieldSkill(sera, 'heal', allen, s.party)).not.toBeNull();
    expect(allen.hp).toBeGreaterThan(5);
    expect(sera.mp).toBe(stats(sera).maxMp - 3);
  });
  it('セーブしてロードすると同じ状態に戻る', () => {
    const m = new Map<string, string>();
    const storage = { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
    const s = newGame();
    s.gold = 1234;
    s.flags.metElder = true;
    saveGame(s, storage);
    expect(loadGame(storage)).toEqual(s);
  });
});
