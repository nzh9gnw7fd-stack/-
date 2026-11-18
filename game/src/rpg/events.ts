/**
 * 話しかけたとき・踏んだときに起きるイベント。
 * マップの npcs[].talk / triggers[].event に書いた名前で呼ばれる。
 */
import type { Script } from '../logic/dialogue';
import { INN_PRICE, type EnemyId } from './data';
import type { GameState } from './state';

export interface EventContext {
  state: GameState;
  /** 会話を表示する */
  say(script: Script, onEnd?: () => void): void;
  /** 一人のセリフを何行か続けて表示する */
  talk(speaker: string | undefined, lines: string[], onEnd?: () => void): void;
  openShop(): void;
  rest(): void;
  battle(enemies: EnemyId[], opts: { boss?: boolean; onWin?: () => void }): void;
  refresh(): void;
  ending(): void;
  healParty(): void;
}

export const EVENTS: Record<string, (ctx: EventContext) => void> = {
  shop: (ctx) => ctx.talk('道具屋', ['いらっしゃい！ 旅の支度ならおまかせを。'], () => ctx.openShop()),

  inn: (ctx) =>
    ctx.say(
      {
        start: {
          speaker: '宿屋',
          text: `旅の宿へようこそ。ひと晩 ${INN_PRICE} ゴールドですが、お泊まりになりますか？（いま ${ctx.state.gold} G）`,
          choices: [
            { text: '泊まる', next: 'yes', set: { _inn: true } },
            { text: 'やめておく', next: 'no' },
          ],
        },
        yes: { speaker: '宿屋', text: 'では、ごゆっくり……' },
        no: { speaker: '宿屋', text: 'またのお越しを。' },
      },
      () => {
        if (!ctx.state.flags._inn) return;
        delete ctx.state.flags._inn;
        if (ctx.state.gold < INN_PRICE) {
          ctx.talk('宿屋', ['おや、お金が足りないようですね……。']);
          return;
        }
        ctx.state.gold -= INN_PRICE;
        ctx.rest();
      },
    ),

  elder: (ctx) => {
    const f = ctx.state.flags;
    if (f.bossDefeated) {
      ctx.talk('村長', [
        'おお……！ その青い輝きは、まさしく『水の石』！',
        'さっそく泉に戻すとしよう。',
      ], () => ctx.ending());
      return;
    }
    if (!f.metElder) {
      ctx.talk('村長', [
        'よく来てくれた。困ったことになってのう。',
        '村の泉が、ある日とつぜん枯れてしまったのじゃ。',
        '北東の洞窟に住みついた『岩喰いのヌシ』が、泉の源『水の石』を飲みこんでしまったらしい。',
        'どうか水の石を取り戻してはくれんか。わずかじゃが、旅の足しにしてくれ。',
      ], () => {
        f.metElder = true;
        ctx.state.gold += 150;
        ctx.talk(undefined, ['150 ゴールドを受け取った！'], () => ctx.refresh());
      });
      return;
    }
    ctx.talk('村長', [
      '洞窟は川をこえた北東にある。橋をわたって道なりに進むのじゃ。',
      'ヌシはおそろしく強い。村の店で装備をととのえ、平原で腕をみがいてから挑むがよい。',
    ]);
  },

  girl: (ctx) =>
    ctx.talk('女の子', ctx.state.flags.bossDefeated
      ? ['泉にお水が戻ったの！ ありがとう！']
      : ['泉のお水、また飲みたいなあ……。']),

  villager: (ctx) =>
    ctx.talk('村人', [
      '平原の森には魔物が多いが、宝箱が隠されているそうだ。',
      'それと、かいふくの呪文はメニューの「じゅもん」から使えるぞ。',
    ]),

  guard: (ctx) =>
    ctx.talk('門番', ctx.state.flags.metElder
      ? ['村の外は魔物が出る。傷ついたら宿屋で休むといい。', 'メニューは X キーか ESC で開ける。セーブもそこからだ。']
      : ['旅のお方、まずは村の真ん中にある村長の家をたずねてみなされ。']),

  traveler: (ctx) =>
    ctx.talk('旅人', [
      'この先の洞窟の奥には、傷を癒やす泉がわいているらしい。',
      'それと……ヌシは3回に1回、岩を降らせる大技を使うそうだ。その前に「ぼうぎょ」で身を守るといい。',
    ]),

  boss: (ctx) =>
    ctx.say(
      {
        start: { speaker: '岩喰いのヌシ', text: 'グオォォ……。この石は、ワシのものだ……。奪いにきたのなら、おまえたちも喰ってやる……！', next: 'q' },
        q: {
          text: 'ヌシと戦いますか？',
          choices: [
            { text: '戦う', next: 'go', set: { _fight: true } },
            { text: 'まだやめておく', next: 'later' },
          ],
        },
        go: { speaker: '岩喰いのヌシ', text: 'グオオオオオッ！！' },
        later: { text: '（いったん引き返そう……）' },
      },
      () => {
        if (!ctx.state.flags._fight) return;
        delete ctx.state.flags._fight;
        ctx.battle(['golem'], {
          boss: true,
          onWin: () => {
            ctx.state.flags.bossDefeated = true;
            ctx.refresh();
            ctx.talk(undefined, [
              'ヌシは音をたてて崩れおちた……。',
              'がれきの中から、青く光る石がころがり出た。',
              '『水の石』を手に入れた！ 村長のもとへ戻ろう。',
            ]);
          },
        });
      },
    ),

  spring: (ctx) => {
    ctx.healParty();
    ctx.talk(undefined, ['泉の水を飲んだ。', 'HPとMPがすっかり回復した！']);
  },

  bossRoom: (ctx) => {
    const f = ctx.state.flags;
    if (f.bossDefeated || f.bossWarned) return;
    f.bossWarned = true;
    ctx.talk(undefined, ['奥から地鳴りがひびいてくる……。', '何か、とても大きなものがいる！']);
  },
};
