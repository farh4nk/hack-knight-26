import { SIMULATE_RESTLESS_MS, TELEMETRY_HZ } from "./config";
import type { CameraStatus, NightVisionMode, SleepState, Telemetry } from "./types";

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

const NIGHT_VISION_MODES: NightVisionMode[] = ["OFF", "AUTO", "ON"];

function cameraFor(state: SleepState, mode: NightVisionMode): CameraStatus {
  const base: CameraStatus = {
    live: true,
    gate: state === "SIGNAL_UNSTABLE" ? "CLOSED" : "OPEN",
    framing: state === "SIGNAL_UNSTABLE" ? "NO_CHEST_ROOM" : "OK",
    sdk_code: state === "SIGNAL_UNSTABLE" ? "kFaceTooLow" : null,
    sdk_hint: state === "SIGNAL_UNSTABLE" ? "Move up, or tilt the camera down." : null,
    night_vision: mode,
    enhancing: mode !== "OFF" && state !== "SIGNAL_UNSTABLE",
  };
  return base;
}

const CAMERA: Record<SleepState, Record<NightVisionMode, CameraStatus>> = {
  ASLEEP: {
    OFF: cameraFor("ASLEEP", "OFF"),
    AUTO: cameraFor("ASLEEP", "AUTO"),
    ON: cameraFor("ASLEEP", "ON"),
  },
  DROWSY: {
    OFF: cameraFor("DROWSY", "OFF"),
    AUTO: cameraFor("DROWSY", "AUTO"),
    ON: cameraFor("DROWSY", "ON"),
  },
  RESTLESS: {
    OFF: cameraFor("RESTLESS", "OFF"),
    AUTO: cameraFor("RESTLESS", "AUTO"),
    ON: cameraFor("RESTLESS", "ON"),
  },
  AWAKE: {
    OFF: cameraFor("AWAKE", "OFF"),
    AUTO: cameraFor("AWAKE", "AUTO"),
    ON: cameraFor("AWAKE", "ON"),
  },
  SIGNAL_UNSTABLE: {
    OFF: cameraFor("SIGNAL_UNSTABLE", "OFF"),
    AUTO: cameraFor("SIGNAL_UNSTABLE", "AUTO"),
    ON: cameraFor("SIGNAL_UNSTABLE", "ON"),
  },
};

const jitter = (base: number, spread: number) =>
  base + (Math.random() - 0.5) * 2 * spread;

let nightVisionModeIndex = 0;

export interface MockTelemetrySource {
  stop: () => void;
  simulateRestless: () => void;
}

export function startMockTelemetry(
  onMessage: (t: Telemetry) => void,
): MockTelemetrySource {
  const startedAt = Date.now();
  const cycleSeconds = SCRIPT.reduce((sum, s) => sum + s.seconds, 0);
  let restlessUntil = 0;

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
    const mode = NIGHT_VISION_MODES[nightVisionModeIndex % NIGHT_VISION_MODES.length];
    nightVisionModeIndex++;
    onMessage({
      timestamp: new Date().toISOString(),
      state,
      vitals: {
        brpm: Math.max(0, Number(jitter(p.brpm, 1.5).toFixed(1))),
        bpm: Math.max(0, Math.round(jitter(p.bpm, 4))),
        confidence: Number(jitter(p.confidence, 0.05).toFixed(2)),
      },
      motion_index: Number(Math.max(0, jitter(p.motion, 0.05)).toFixed(2)),
      camera: CAMERA[state][mode],
    });
  }, 1000 / TELEMETRY_HZ);

  return {
    stop: () => clearInterval(timer),
    simulateRestless: () => {
      restlessUntil = Date.now() + SIMULATE_RESTLESS_MS;
    },
  };
}
