import type { Script } from '../logic/dialogue';

/**
 * ノベルのシナリオ。ノードを増やすだけで話を書き足せる。
 *  - next: 次のノード   - choices: 選択肢   - set: フラグを立てる   - if: 選択肢の表示条件
 *  - redirect: ['フラグ', 'ノード'] フラグが立っていたら別のノードへ
 *  - bg: 背景色   - portrait: 立ち絵（ここでは色）
 */
export const NOVEL_SCRIPT: Script = {
  start: { bg: '#3e2723', text: '――放課後。誰もいないはずの部室に、明かりがついていた。', next: 'door' },
  door: {
    bg: '#3e2723', text: 'どうする？',
    choices: [
      { text: 'ドアを開ける', next: 'open' },
      { text: 'ノックする', next: 'knock', set: { polite: true } },
    ],
  },
  knock: { bg: '#3e2723', text: 'コンコン。……返事はない。そっとドアを開けた。', next: 'open' },
  open: { bg: '#1a237e', speaker: '???', portrait: '#f48fb1', text: 'あっ……！ ご、ごめんなさい、勝手に入っちゃって。', next: 'intro' },
  intro: { bg: '#1a237e', speaker: 'ミナ', portrait: '#f48fb1', text: 'わたし、ミナ。ここでゲームを作ってみたくて……。', redirect: ['polite', 'introPolite'], next: 'ask' },
  introPolite: { bg: '#1a237e', speaker: 'ミナ', portrait: '#f48fb1', text: 'ノックしてくれたんだね。ありがとう。わたし、ミナ。ここでゲームを作ってみたくて……。', next: 'ask', set: { trust: true } },
  ask: {
    bg: '#1a237e', speaker: 'ミナ', portrait: '#f48fb1', text: 'よかったら、一緒に作らない？',
    choices: [
      { text: 'もちろん！', next: 'yes' },
      { text: 'どんなゲーム？', next: 'what' },
      { text: '（ノックした君だから）秘密を打ち明ける', next: 'secret', if: 'trust' },
    ],
  },
  what: { bg: '#1a237e', speaker: 'ミナ', portrait: '#f48fb1', text: 'それをこれから決めるの！ アクションでも、パズルでも、RPG でも。', next: 'ask' },
  secret: { bg: '#4a148c', speaker: 'ミナ', portrait: '#ce93d8', text: '……実はね、このサンプルは「フラグ」で会話が変わるんだよ。ノックしたから、この選択肢が出たの。', next: 'yes' },
  yes: { bg: '#004d40', speaker: 'ミナ', portrait: '#80cbc4', text: 'やった！ じゃあ、明日からよろしくね！', next: 'end' },
  end: { bg: '#000000', text: '―― おしまい ――（data/novelScript.ts を書き換えて、自分の物語を作ろう）' },
};
