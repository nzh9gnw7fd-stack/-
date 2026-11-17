/**
 * 効果音をその場で合成する（音声ファイル不要）。
 * 本格的な BGM/効果音ファイルを使う場合は Phaser の this.load.audio() と this.sound.play() を使う。
 */
import { loadData, saveData } from './save';

let ctx: AudioContext | null = null;
let muted = loadData('muted', false);

function audio(): AudioContext | null {
  if (muted) return null;
  if (!ctx) {
    const C = globalThis.AudioContext ?? (globalThis as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!C) return null;
    ctx = new C();
  }
  if (ctx.state === 'suspended') void ctx.resume();
  return ctx;
}

function tone(freq: number, endFreq: number, dur: number, type: OscillatorType = 'square', vol = 0.12, delay = 0): void {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime + delay;
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  osc.frequency.exponentialRampToValueAtTime(Math.max(1, endFreq), t + dur);
  gain.gain.setValueAtTime(vol, t);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(gain).connect(ac.destination);
  osc.start(t);
  osc.stop(t + dur);
}

function noise(dur: number, vol = 0.2): void {
  const ac = audio();
  if (!ac) return;
  const len = Math.floor(ac.sampleRate * dur);
  const buf = ac.createBuffer(1, len, ac.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
  const src = ac.createBufferSource();
  const gain = ac.createGain();
  gain.gain.value = vol;
  src.buffer = buf;
  src.connect(gain).connect(ac.destination);
  src.start();
}

export const sfx = {
  coin: () => { tone(988, 988, 0.06); tone(1319, 1319, 0.15, 'square', 0.12, 0.06); },
  jump: () => tone(250, 700, 0.15),
  shoot: () => tone(1200, 200, 0.08, 'sawtooth', 0.05),
  hit: () => noise(0.12, 0.25),
  explode: () => noise(0.45, 0.35),
  select: () => tone(660, 660, 0.05, 'triangle', 0.15),
  cancel: () => tone(330, 220, 0.08, 'triangle', 0.15),
  powerup: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, f, 0.1, 'square', 0.1, i * 0.07)),
  lose: () => tone(440, 80, 0.7, 'triangle', 0.2),
  text: () => tone(1500, 1500, 0.015, 'square', 0.03),
};

export function isMuted(): boolean {
  return muted;
}

export function setMuted(value: boolean): void {
  muted = value;
  saveData('muted', value);
}
