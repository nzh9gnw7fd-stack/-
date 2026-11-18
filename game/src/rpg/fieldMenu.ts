/**
 * フィールドのメニュー（つよさ・どうぐ・じゅもん・そうび・セーブ）と、道具屋。
 */
import type Phaser from 'phaser';
import type { GameInput } from '../core/input';
import { sfx } from '../core/sfx';
import { EQUIPS, ITEMS, MEMBERS, SHOP_ITEMS, SKILLS, expForLevel, type EquipId, type ItemId, type SkillId } from './data';
import { addEquip, addItem, castFieldSkill, equip, game, saveGame, skillsOf, stats, useItemOn, type Member } from './state';
import { SelectList, UIStack, Win, textStyle, type ListItem } from './ui';

/** 画面下に少しだけ出るメッセージ */
export function toast(scene: Phaser.Scene, msg: string): void {
  // 文字の長さに合わせて幅を決める
  const probe = scene.add.text(0, 0, msg, textStyle(20));
  const width = Math.min(760, Math.max(300, probe.width + 48));
  probe.destroy();
  const w = new Win(scene, (800 - width) / 2, 372, width, 56);
  w.text(width / 2, 16, msg, 20).setOrigin(0.5, 0);
  w.root.setDepth(4000);
  scene.time.delayedCall(1400, () => w.destroy());
}

function partyWindow(scene: Phaser.Scene, x: number, y: number): { win: Win; refresh: () => void } {
  const win = new Win(scene, x, y, 552, 128);
  const refresh = () => {
    win.clear();
    game.state.party.forEach((m, i) => {
      const s = stats(m);
      const cx = 16 + i * 180;
      const dead = m.hp <= 0;
      win.text(cx, 12, MEMBERS[m.id].name, 20, dead ? '#ef5350' : '#ffffff');
      win.text(cx, 40, `Lv ${m.level}  ${MEMBERS[m.id].job}`, 15, '#b0bec5');
      win.text(cx, 64, `HP ${m.hp}/${s.maxHp}`, 18, dead ? '#ef5350' : m.hp < s.maxHp / 4 ? '#ffb74d' : '#ffffff');
      win.text(cx, 90, `MP ${m.mp}/${s.maxMp}`, 18);
    });
  };
  refresh();
  return { win, refresh };
}

function goldWindow(scene: Phaser.Scene, x: number, y: number): { win: Win; refresh: () => void } {
  const win = new Win(scene, x, y, 200, 50);
  const t = win.text(184, 13, '', 20).setOrigin(1, 0);
  const refresh = () => t.setText(`${game.state.gold} G`);
  refresh();
  return { win, refresh };
}

/** 仲間を1人選ぶ */
function chooseMember(scene: Phaser.Scene, ui: UIStack, title: string, onPick: (m: Member) => void, filter?: (m: Member) => boolean): void {
  const items: ListItem[] = game.state.party.map((m) => ({
    label: MEMBERS[m.id].name,
    right: `HP ${m.hp}`,
    disabled: filter ? !filter(m) : false,
    onSelect: () => onPick(m),
  }));
  const list = new SelectList(scene, 240, 160, 260, items, { title });
  list.onCancel = () => ui.pop();
  ui.push(list);
}

export function openFieldMenu(scene: Phaser.Scene, ui: UIStack, onClose: () => void): void {
  const party = partyWindow(scene, 232, 16);
  const gold = goldWindow(scene, 16, 290);
  const refreshAll = () => { party.refresh(); gold.refresh(); };
  const close = () => { ui.clear(); onClose(); };

  const main = new SelectList(scene, 16, 16, 200, [
    { label: 'つよさ', onSelect: () => chooseMember(scene, ui, 'だれの？', (m) => showStatus(scene, ui, m)) },
    { label: 'どうぐ', onSelect: () => itemMenu(scene, ui, refreshAll) },
    { label: 'じゅもん', onSelect: () => spellMenu(scene, ui, refreshAll) },
    { label: 'そうび', onSelect: () => chooseMember(scene, ui, 'だれの？', (m) => equipMenu(scene, ui, m, refreshAll)) },
    { label: 'セーブ', onSelect: () => toast(scene, saveGame(game.state) ? 'セーブしました。' : 'セーブできませんでした。') },
    { label: 'とじる', onSelect: close },
  ]);
  main.onCancel = close;
  ui.push(main, [party.win, gold.win]);
}

function showStatus(scene: Phaser.Scene, ui: UIStack, m: Member): void {
  const s = stats(m);
  const def = MEMBERS[m.id];
  const w = new Win(scene, 120, 60, 560, 440);
  w.text(24, 18, `${def.name}（${def.job}）  Lv ${m.level}`, 24, '#ffd54f');
  const rows: [string, string][] = [
    ['HP', `${m.hp} / ${s.maxHp}`], ['MP', `${m.mp} / ${s.maxMp}`],
    ['こうげき', `${s.atk}`], ['ぼうぎょ', `${s.def}`], ['まりょく', `${s.mag}`], ['すばやさ', `${s.agi}`],
    ['けいけんち', `${m.exp}`], ['つぎのレベルまで', `${Math.max(0, expForLevel(m.level + 1) - m.exp)}`],
  ];
  rows.forEach(([k, v], i) => {
    w.text(24, 64 + i * 30, k, 18, '#b0bec5');
    w.text(250, 64 + i * 30, v, 18).setOrigin(1, 0);
  });
  w.text(290, 64, 'ぶき', 16, '#b0bec5');
  w.text(290, 86, m.weapon ? EQUIPS[m.weapon].name : '（なし）', 18);
  w.text(290, 120, 'よろい', 16, '#b0bec5');
  w.text(290, 142, m.armor ? EQUIPS[m.armor].name : '（なし）', 18);
  w.text(290, 180, 'おぼえた技', 16, '#b0bec5');
  const skills = skillsOf(m);
  (skills.length ? skills : [null]).forEach((id, i) => w.text(290, 202 + i * 26, id ? `${SKILLS[id].name}（MP${SKILLS[id].mp}）` : '（なし）', 17));
  w.text(280, 404, '決定 / キャンセルでもどる', 14, '#90a4ae').setOrigin(0.5, 0);
  ui.push(null, [w], (input: GameInput) => {
    if (input.actionPressed || input.cancelPressed) ui.pop();
  });
  scene.input.once('pointerdown', () => ui.top?.wins.includes(w) && ui.pop());
}

function itemMenu(scene: Phaser.Scene, ui: UIStack, refresh: () => void): void {
  const build = (): ListItem[] =>
    (Object.entries(game.state.items) as [ItemId, number][]).map(([id, n]) => ({
      label: ITEMS[id].name,
      right: `×${n}`,
      onSelect: () => {
        const def = ITEMS[id];
        chooseMember(scene, ui, `${def.name}をだれに？`, (m) => {
          const msg = useItemOn(game.state, id, m);
          if (!msg) { sfx.cancel(); toast(scene, 'その人には使えません。'); return; }
          sfx.powerup();
          toast(scene, msg);
          refresh();
          ui.pop();
          list.setItems(build());
        });
      },
    }));
  const list = new SelectList(scene, 240, 160, 320, build(), { title: 'どうぐ', visibleRows: 6 });
  list.onCancel = () => ui.pop();
  ui.push(list);
}

function spellMenu(scene: Phaser.Scene, ui: UIStack, refresh: () => void): void {
  const fieldSkills = (m: Member) => skillsOf(m).filter((id) => ['heal', 'revive'].includes(SKILLS[id].kind));
  chooseMember(scene, ui, 'だれがとなえる？', (caster) => {
    const build = (): ListItem[] => fieldSkills(caster).map((id: SkillId) => ({
      label: SKILLS[id].name,
      right: `MP ${SKILLS[id].mp}`,
      disabled: caster.mp < SKILLS[id].mp,
      onSelect: () => {
        const cast = (target: Member) => {
          const msg = castFieldSkill(caster, id, target, game.state.party);
          if (!msg) { sfx.cancel(); toast(scene, 'しかし、効果がなかった。'); return; }
          sfx.powerup();
          toast(scene, msg);
          refresh();
          list.setItems(build());
        };
        if (SKILLS[id].target === 'allAllies') cast(caster);
        else chooseMember(scene, ui, 'だれに？', (t) => { cast(t); ui.pop(); });
      },
    }));
    const list = new SelectList(scene, 240, 200, 320, build(), { title: `${MEMBERS[caster.id].name}のじゅもん` });
    list.onCancel = () => ui.pop();
    ui.push(list);
  }, (m) => m.hp > 0 && fieldSkills(m).length > 0);
}

function bonusText(id: EquipId): string {
  const names: Record<string, string> = { atk: 'こう', def: 'ぼう', mag: 'まりょく', agi: 'すば', maxHp: 'HP', maxMp: 'MP' };
  return Object.entries(EQUIPS[id].bonus).map(([k, v]) => `${names[k]}+${v}`).join(' ');
}

function equipMenu(scene: Phaser.Scene, ui: UIStack, m: Member, refresh: () => void): void {
  const slotItems = (): ListItem[] => (['weapon', 'armor'] as const).map((slot) => ({
    label: slot === 'weapon' ? 'ぶき' : 'よろい',
    right: m[slot] ? EQUIPS[m[slot]!].name : '（なし）',
    onSelect: () => {
      const choices: ListItem[] = (Object.entries(game.state.equips) as [EquipId, number][])
        .filter(([id]) => EQUIPS[id].slot === slot && EQUIPS[id].for.includes(m.id))
        .map(([id, n]) => ({
          label: `${EQUIPS[id].name}${n > 1 ? ` ×${n}` : ''}`,
          right: bonusText(id),
          onSelect: () => { equip(game.state, m, slot, id); sfx.powerup(); done(); },
        }));
      choices.push({ label: 'はずす', onSelect: () => { equip(game.state, m, slot, null); done(); } });
      const done = () => { refresh(); ui.pop(); slots.setItems(slotItems()); };
      const list = new SelectList(scene, 200, 240, 420, choices, { title: '持っている装備', visibleRows: 6 });
      list.onCancel = () => ui.pop();
      ui.push(list);
    },
  }));
  const slots = new SelectList(scene, 240, 160, 360, slotItems(), { title: `${MEMBERS[m.id].name}のそうび` });
  slots.onCancel = () => ui.pop();
  ui.push(slots);
}

export function openShop(scene: Phaser.Scene, ui: UIStack, onClose: () => void): void {
  const gold = goldWindow(scene, 584, 16);
  const info = new Win(scene, 16, 440, 768, 64);
  const infoText = info.text(16, 20, '', 18);
  const items: ListItem[] = SHOP_ITEMS.map((s) => {
    const def = s.kind === 'item' ? ITEMS[s.id] : EQUIPS[s.id];
    return {
      label: def.name,
      right: `${def.price} G`,
      onSelect: () => {
        if (game.state.gold < def.price) { sfx.cancel(); toast(scene, 'お金が足りないようです。'); return; }
        game.state.gold -= def.price;
        if (s.kind === 'item') addItem(game.state, s.id);
        else addEquip(game.state, s.id);
        sfx.coin();
        gold.refresh();
        toast(scene, s.kind === 'equip' ? `${def.name}を買った！（メニューの「そうび」で装備）` : `${def.name}を買った！`);
      },
    };
  });
  const describe = (i: number) => {
    const s = SHOP_ITEMS[i];
    if (s.kind === 'item') infoText.setText(ITEMS[s.id].desc);
    else infoText.setText(`${bonusText(s.id)}　装備できる: ${EQUIPS[s.id].for.map((id) => MEMBERS[id].name).join('・')}`);
  };
  const list = new SelectList(scene, 16, 16, 420, items, { title: 'なにを買いますか？', visibleRows: 9 });
  list.onMove = describe;
  describe(0);
  list.onCancel = () => { ui.clear(); onClose(); };
  ui.push(list, [gold.win, info]);
}
