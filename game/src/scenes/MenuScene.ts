import Phaser from 'phaser';
import { GAME_WIDTH } from '../config';
import { isMuted, setMuted } from '../core/sfx';
import { button, text } from '../core/ui';

interface Entry { key: string; label: string; desc: string }

const SAMPLES: Entry[] = [
  { key: 'CoinDash', label: 'トップダウン', desc: 'コイン集め / 状態管理' },
  { key: 'Platformer', label: 'アクション', desc: '横スクロール / タイルマップ' },
  { key: 'Shooter', label: 'シューティング', desc: '弾幕 / パーティクル' },
  { key: 'Match3', label: 'パズル', desc: 'マッチ3 / 盤面ロジック' },
  { key: 'Field', label: 'RPG フィールド', desc: '地形生成 / 経路探索 / 会話' },
  { key: 'Roguelike', label: 'ローグライク', desc: 'ダンジョン生成 / 視界 / ターン制' },
  { key: 'Physics', label: '物理演算', desc: 'Matter.js / 積み木崩し' },
  { key: 'Novel', label: 'ノベル / ADV', desc: '分岐シナリオ / フラグ' },
  { key: '3D', label: '3D（three.js）', desc: '3D 空間 / ライト / 影' },
];

export class MenuScene extends Phaser.Scene {
  constructor() {
    super('Menu');
  }

  create(): void {
    text(this, GAME_WIDTH / 2, 50, 'GAME LAB', 48, '#ffd54f').setOrigin(0.5).setFontStyle('bold');
    text(this, GAME_WIDTH / 2, 100, 'ジャンル別サンプル集 — コピーして自分のゲームの土台にしよう', 16, '#b0bec5').setOrigin(0.5);

    const cols = 3;
    const w = 230;
    const h = 100;
    SAMPLES.forEach((s, i) => {
      const x = GAME_WIDTH / 2 + ((i % cols) - 1) * (w + 20);
      const y = 190 + Math.floor(i / cols) * (h + 20);
      button(this, x, y, w, h, s.label, () => {
        if (s.key === '3D') window.location.href = './3d.html';
        else this.scene.start(s.key);
      }, s.desc);
    });

    const sound = text(this, GAME_WIDTH / 2, 545, '', 16, '#90a4ae').setOrigin(0.5).setInteractive({ useHandCursor: true });
    const refresh = () => sound.setText(`サウンド: ${isMuted() ? 'OFF' : 'ON'}（M キー / クリックで切替）`);
    const toggle = () => { setMuted(!isMuted()); refresh(); };
    sound.on('pointerdown', toggle);
    this.input.keyboard?.on('keydown-M', toggle);
    refresh();
    text(this, GAME_WIDTH / 2, 575, 'キーボード・ゲームパッド・タッチ操作に対応', 14, '#607d8b').setOrigin(0.5);
  }
}
