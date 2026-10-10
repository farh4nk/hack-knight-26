import { SIMULATE_RESTLESS_MS, TELEMETRY_HZ } from "./config";
import type { CameraStatus, SleepState, Telemetry } from "./types";

// Scripted cycle so every badge state shows up within about a minute.
const SCRIPT: { state: SleepState; seconds: number }[] = [
  { state: "ASLEEP", seconds: 20 },
  { state: "DROWSY", seconds: 8 },
  { state: "RESTLESS", seconds: 8 },
  { state: "AWAKE", seconds: 8 },
  { state: "SIGNAL_UNSTABLE", seconds: 6 },
  { state: "DROWSY", seconds: 6 },
];

const PROFILE: Record<
  SleepState,
  { brpm: number; bpm: number; motion: number; confidence: number }
> = {
  ASLEEP: { brpm: 26, bpm: 110, motion: 0.05, confidence: 0.9 },
  DROWSY: { brpm: 30, bpm: 118, motion: 0.15, confidence: 0.85 },
  RESTLESS: { brpm: 38, bpm: 135, motion: 0.7, confidence: 0.7 },
  AWAKE: { brpm: 42, bpm: 145, motion: 0.85, confidence: 0.75 },
  SIGNAL_UNSTABLE: { brpm: 0, bpm: 0, motion: 0.3, confidence: 0.2 },
};

// Camera status per state; SIGNAL_UNSTABLE shows a Presage hint like the real daemon.
const CAMERA: Record<SleepState, CameraStatus> = {
  ASLEEP: { live: true, gate: "OPEN", framing: "OK", sdk_code: null, sdk_hint: null },
  DROWSY: { live: true, gate: "OPEN", framing: "OK", sdk_code: null, sdk_hint: null },
  RESTLESS: { live: true, gate: "OPEN", framing: "OK", sdk_code: null, sdk_hint: null },
  AWAKE: { live: true, gate: "OPEN", framing: "OK", sdk_code: null, sdk_hint: null },
  SIGNAL_UNSTABLE: {
    live: true,
    gate: "CLOSED",
    framing: "NO_CHEST_ROOM",
    sdk_code: "kFaceTooLow",
    sdk_hint: "Move up, or tilt the camera down.",
  },
};

const jitter = (base: number, spread: number) =>
  base + (Math.random() - 0.5) * 2 * spread;

export interface MockTelemetrySource {
  stop: () => void;
  simulateRestless: () => void;
  setCameraEnabled: (enabled: boolean) => void;
}

export function startMockTelemetry(
  onMessage: (t: Telemetry) => void,
): MockTelemetrySource {
  const startedAt = Date.now();
  const cycleSeconds = SCRIPT.reduce((sum, s) => sum + s.seconds, 0);
  let restlessUntil = 0;
  let cameraOn = true;

  const scriptedState = (): SleepState => {
    let t = ((Date.now() - startedAt) / 1000) % cycleSeconds;
    for (const step of SCRIPT) {
      if (t < step.seconds) return step.state;
      t -= step.seconds;
    }
    return "ASLEEP";
  };

  const timer = setInterval(() => {
    const state = Date.now() < restlessUntil ? "RESTLESS" : scriptedState();
    const p = PROFILE[state];
    onMessage({
      timestamp: new Date().toISOString(),
      state,
      mode: "SIMULATED",
      vitals: {
        brpm: Math.max(0, Number(jitter(p.brpm, 1.5).toFixed(1))),
        bpm: Math.max(0, Math.round(jitter(p.bpm, 4))),
        confidence: Number(jitter(p.confidence, 0.05).toFixed(2)),
      },
      motion_index: Number(Math.max(0, jitter(p.motion, 0.05)).toFixed(2)),
      camera: {
        ...CAMERA[state],
        enabled: cameraOn,
        live: cameraOn,
      },
    });
  }, 1000 / TELEMETRY_HZ);

  return {
    stop: () => clearInterval(timer),
    simulateRestless: () => {
      restlessUntil = Date.now() + SIMULATE_RESTLESS_MS;
    },
    setCameraEnabled: (enabled) => {
      cameraOn = enabled;
    },
  };
}
