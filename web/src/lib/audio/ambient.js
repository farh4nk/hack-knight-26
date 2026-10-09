// Synthesizes a looping heartbeat + soft pad as a WAV so no audio asset is needed.
// The result is played through a plain HTMLAudioElement (Task 3.3).

const SAMPLE_RATE = 22050;

function thump(buf, startSec, freq, amp) {
  const start = Math.floor(startSec * SAMPLE_RATE);
  const len = Math.floor(0.18 * SAMPLE_RATE);
  for (let i = 0; i < len && start + i < buf.length; i++) {
    const t = i / SAMPLE_RATE;
    const env = Math.exp(-t * 28);
    buf[start + i] += Math.sin(2 * Math.PI * (freq - 25 * t) * t) * env * amp;
  }
}

export function createHeartbeatWavUrl(bpm = 66, seconds = 12) {
  const beatLen = 60 / bpm;
  const beats = Math.round(seconds / beatLen); // whole beats => seamless loop
  const total = Math.floor(beats * beatLen * SAMPLE_RATE);
  const buf = new Float32Array(total);

  for (let b = 0; b < beats; b++) {
    const t0 = b * beatLen;
    thump(buf, t0, 60, 0.9); // "lub"
    thump(buf, t0 + 0.28, 50, 0.6); // "dub"
  }

  const loopSec = total / SAMPLE_RATE;
  const f1 = Math.round(110 * loopSec) / loopSec;
  const f2 = Math.round(165 * loopSec) / loopSec;
  for (let i = 0; i < total; i++) {
    const t = i / SAMPLE_RATE;
    buf[i] += 0.05 * Math.sin(2 * Math.PI * f1 * t) + 0.03 * Math.sin(2 * Math.PI * f2 * t);
  }

  return URL.createObjectURL(encodeWav(buf));
}

function encodeWav(samples) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const write = (o, s) => [...s].forEach((c, i) => view.setUint8(o + i, c.charCodeAt(0)));
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, SAMPLE_RATE, true);
  view.setUint32(28, SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => {
    const c = Math.max(-1, Math.min(1, s));
    view.setInt16(44 + i * 2, c < 0 ? c * 0x8000 : c * 0x7fff, true);
  });
  return new Blob([view], { type: "audio/wav" });
}
