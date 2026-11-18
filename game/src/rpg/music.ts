/**
 * 簡易 BGM（Web Audio でその場で演奏する 8bit 風の曲）。
 * 本格的な曲を使うときは、音声ファイルを this.load.audio() で読み込み this.sound.play() に置き換える。
 */
import { isMuted } from '../core/sfx';

type Note = [number | null, number]; // [MIDI 番号 or 休符, 長さ(16分音符の数)]
interface Track { bpm: number; melody: Note[]; bass: Note[]; wave?: OscillatorType }

const n = (s: string): Note[] =>
  s.trim().split(/\s+/).map((tok) => {
    const [p, len] = tok.split(':');
    return [p === '-' ? null : Number(p), Number(len ?? 2)];
  });

export const TRACKS: Record<string, Track> = {
  title: {
    bpm: 84,
    melody: n('67:4 72:4 74:4 76:8 74:2 72:2 74:4 79:4 76:8 -:4 72:4 74:4 76:4 77:4 76:4 74:4 72:12 -:4'),
    bass: n('48:8 55:8 53:8 55:8 48:8 55:8 53:8 48:8'),
  },
  town: {
    bpm: 110,
    melody: n('72:2 76:2 79:2 76:2 77:4 74:4 76:2 72:2 74:2 71:2 72:8 72:2 76:2 79:2 81:2 79:4 77:2 76:2 74:4 76:2 74:2 72:8'),
    bass: n('48:4 55:4 53:4 50:4 48:4 55:4 48:8 48:4 55:4 53:4 55:4 50:4 55:4 48:8'),
    wave: 'triangle',
  },
  field: {
    bpm: 132,
    melody: n('67:2 72:2 76:4 74:2 72:2 74:4 76:2 79:2 81:4 79:4 -:2 77:2 76:2 74:2 72:4 74:2 76:2 72:8 -:4'),
    bass: n('48:4 48:4 53:4 53:4 55:4 55:4 48:4 55:4 53:4 53:4 55:4 55:4 48:8 48:8'),
  },
  cave: {
    bpm: 90,
    melody: n('57:4 60:4 63:4 62:4 60:8 -:4 57:4 60:4 64:4 63:8 -:8 56:4 59:4 62:4 60:4 57:12 -:4'),
    bass: n('45:8 45:8 44:8 44:8 41:8 41:8 45:16'),
    wave: 'sawtooth',
  },
  battle: {
    bpm: 168,
    melody: n('69:2 69:2 72:2 69:2 76:4 74:2 72:2 71:2 72:2 74:2 71:2 69:4 64:4 69:2 69:2 72:2 76:2 79:4 77:2 76:2 74:2 76:2 72:2 74:2 69:8'),
    bass: n('45:2 57:2 45:2 57:2 45:2 57:2 45:2 57:2 43:2 55:2 43:2 55:2 40:2 52:2 40:2 52:2 41:2 53:2 41:2 53:2 43:2 55:2 43:2 55:2 45:2 57:2 45:2 57:2 45:2 57:2 45:2 57:2'),
  },
  boss: {
    bpm: 150,
    melody: n('62:2 63:2 62:2 63:2 66:4 65:4 62:2 63:2 62:2 60:2 58:8 62:2 63:2 66:2 69:2 70:4 69:2 66:2 65:2 63:2 62:2 60:2 62:8'),
    bass: n('38:2 38:2 50:2 38:2 38:2 50:2 38:2 50:2 37:2 37:2 49:2 37:2 37:2 49:2 37:2 49:2 36:2 36:2 48:2 36:2 36:2 48:2 36:2 48:2 38:2 38:2 50:2 38:2 38:2 50:2 38:2 50:2'),
    wave: 'sawtooth',
  },
  victory: {
    bpm: 150,
    melody: n('72:2 72:2 72:2 72:6 68:6 70:6 72:4 70:2 72:12'),
    bass: n('48:6 48:6 44:6 46:6 48:12'),
  },
};

let ctx: AudioContext | null = null;
let timer: ReturnType<typeof setInterval> | null = null;
let currentName: string | null = null;
let master: GainNode | null = null;

function midiToFreq(m: number): number {
  return 440 * Math.pow(2, (m - 69) / 12);
}

/** 曲を流す（同じ曲なら何もしない）。loop=false で1回だけ */
export function playMusic(name: string, loop = true): void {
  if (currentName === name) return;
  stopMusic();
  currentName = name;
  if (isMuted()) return;
  const C = globalThis.AudioContext ?? (globalThis as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!C) return;
  ctx ??= new C();
  if (ctx.state === 'suspended') void ctx.resume();
  const ac = ctx;
  master = ac.createGain();
  master.gain.value = 0.06;
  master.connect(ac.destination);
  const out = master;
  const track = TRACKS[name];
  const sixteenth = 60 / track.bpm / 4;
  const voices = [
    { notes: track.melody, i: 0, t: ac.currentTime + 0.05, wave: track.wave ?? 'square', vol: 1 },
    { notes: track.bass, i: 0, t: ac.currentTime + 0.05, wave: 'triangle' as OscillatorType, vol: 1.4 },
  ];
  const schedule = () => {
    for (const v of voices) {
      while (v.t < ac.currentTime + 0.3) {
        if (v.i >= v.notes.length) {
          if (!loop) return;
          v.i = 0;
        }
        const [pitch, len] = v.notes[v.i++];
        const dur = len * sixteenth;
        if (pitch !== null) {
          const osc = ac.createOscillator();
          const g = ac.createGain();
          osc.type = v.wave;
          osc.frequency.value = midiToFreq(pitch);
          g.gain.setValueAtTime(v.vol, v.t);
          g.gain.exponentialRampToValueAtTime(0.001, v.t + dur * 0.95);
          osc.connect(g).connect(out);
          osc.start(v.t);
          osc.stop(v.t + dur);
        }
        v.t += dur;
      }
    }
  };
  schedule();
  timer = setInterval(schedule, 100);
}

export function stopMusic(): void {
  if (timer) clearInterval(timer);
  timer = null;
  master?.disconnect();
  master = null;
  currentName = null;
}

/** ミュート切り替え後に呼ぶと、今の曲を鳴らし直す */
export function refreshMusic(): void {
  const name = currentName;
  stopMusic();
  if (name) playMusic(name);
}
