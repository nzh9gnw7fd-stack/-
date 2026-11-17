/**
 * 会話・ノベルゲーム用のシナリオ実行エンジン（描画とは独立）。
 *
 * シナリオはノードの集まり。各ノードは「誰が・何を言うか」と、次のノード（next）か選択肢（choices）を持つ。
 * set でフラグを立て、if で選択肢の表示条件を指定できる（'flag' / '!flag'）。
 */
export type Flags = Record<string, boolean | number | string>;

export interface Choice {
  text: string;
  next: string;
  if?: string;
  set?: Flags;
}

export interface DialogueNode {
  speaker?: string;
  text: string;
  /** 背景色や立ち絵など、表示側で自由に使う追加情報 */
  bg?: string;
  portrait?: string;
  next?: string;
  choices?: Choice[];
  set?: Flags;
  /** 条件を満たさないときに代わりに進むノード: ['flag', 'ノードid'] */
  redirect?: [string, string];
}

export type Script = Record<string, DialogueNode>;

export function checkCondition(cond: string | undefined, flags: Flags): boolean {
  if (!cond) return true;
  return cond.startsWith('!') ? !flags[cond.slice(1)] : !!flags[cond];
}

export class DialogueRunner {
  private id: string | null;

  constructor(
    private readonly script: Script,
    start = 'start',
    public readonly flags: Flags = {},
  ) {
    this.id = null;
    this.goto(start);
  }

  get node(): DialogueNode | null {
    return this.id ? this.script[this.id] : null;
  }

  get nodeId(): string | null {
    return this.id;
  }

  get finished(): boolean {
    return this.id === null;
  }

  /** 表示条件を満たす選択肢だけを返す */
  get choices(): Choice[] {
    return (this.node?.choices ?? []).filter((c) => checkCondition(c.if, this.flags));
  }

  /** 選択肢のないノードで次へ進む */
  advance(): DialogueNode | null {
    const node = this.node;
    if (!node) return null;
    if (this.choices.length > 0) throw new Error('選択肢のあるノードでは choose() を使ってください');
    this.goto(node.next ?? null);
    return this.node;
  }

  choose(index: number): DialogueNode | null {
    const choice = this.choices[index];
    if (!choice) throw new Error(`選択肢 ${index} はありません`);
    Object.assign(this.flags, choice.set);
    this.goto(choice.next);
    return this.node;
  }

  private goto(id: string | null): void {
    // redirect の連鎖をたどって、実際に表示するノードを決める
    for (let guard = 0; id !== null && guard < 100; guard++) {
      const node = this.script[id];
      if (!node) throw new Error(`ノード "${id}" が見つかりません`);
      if (node.redirect && checkCondition(node.redirect[0], this.flags)) {
        id = node.redirect[1];
        continue;
      }
      Object.assign(this.flags, node.set);
      break;
    }
    this.id = id;
  }
}
