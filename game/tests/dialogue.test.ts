import { describe, expect, it } from 'vitest';
import { DialogueRunner, type Script } from '../src/logic/dialogue';

const script: Script = {
  start: { text: 'こんにちは', next: 'q' },
  q: {
    text: 'どうする？',
    choices: [
      { text: 'はい', next: 'yes', set: { agreed: true } },
      { text: '秘密', next: 'secret', if: 'agreed' },
      { text: 'いいえ', next: 'no' },
    ],
  },
  yes: { text: 'やった', redirect: ['met', 'again'], set: { met: true } },
  again: { text: 'また会ったね' },
  secret: { text: 'ひみつ' },
  no: { text: '残念', next: 'q' },
};

describe('DialogueRunner', () => {
  it('next で進み、最後に終わる', () => {
    const r = new DialogueRunner({ start: { text: 'a', next: 'b' }, b: { text: 'b' } });
    expect(r.node?.text).toBe('a');
    r.advance();
    expect(r.node?.text).toBe('b');
    r.advance();
    expect(r.finished).toBe(true);
  });
  it('if の条件で選択肢が出たり消えたりする', () => {
    const r = new DialogueRunner(script);
    r.advance();
    expect(r.choices.map((c) => c.text)).toEqual(['はい', 'いいえ']);
    r.choose(0);
    expect(r.flags.agreed).toBe(true);
    expect(r.node?.text).toBe('やった');
  });
  it('redirect でフラグに応じて分岐する', () => {
    const r = new DialogueRunner(script, 'yes', { met: true });
    expect(r.node?.text).toBe('また会ったね');
  });
  it('選択肢があるノードで advance するとエラー', () => {
    const r = new DialogueRunner(script, 'q');
    expect(() => r.advance()).toThrow();
  });
  it('存在しないノードはエラー', () => {
    expect(() => new DialogueRunner({ start: { text: 'x', next: 'nope' } }).advance()).toThrow(/nope/);
  });
});
