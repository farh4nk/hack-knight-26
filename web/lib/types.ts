// Shared telemetry contract, emitted by the daemon over WS /ws/telemetry at 2 Hz.
export type SleepState =
  | "ASLEEP"
  | "DROWSY"
  | "RESTLESS"
  | "AWAKE"
  | "SIGNAL_UNSTABLE";

export interface Vitals {
  brpm: number;
  bpm: number;
  confidence: number;
}

export type CameraGate = "OPEN" | "CLOSED" | "DISABLED";

export type CameraFraming =
  | "OK"
  | "NO_FACE"
  | "MULTIPLE_FACES"
  | "TOO_SMALL"
  | "OFF_CENTER"
  | "NO_CHEST_ROOM"
  | "UNKNOWN";

export type NightVisionMode = "OFF" | "AUTO" | "ON";

export interface CameraStatus {
  live: boolean;
  gate: CameraGate;
  framing: CameraFraming;
  sdk_code: string | null;
  sdk_hint: string | null;
  night_vision?: NightVisionMode;
  enhancing?: boolean;
}

export interface Telemetry {
  timestamp: string; // ISO 8601
  state: SleepState;
  vitals: Vitals;
  motion_index: number;
  camera?: CameraStatus; // additive; older daemons omit it
}

export const SLEEP_STATES: readonly SleepState[] = [
  "ASLEEP",
  "DROWSY",
  "RESTLESS",
  "AWAKE",
  "SIGNAL_UNSTABLE",
];

export function isTelemetry(value: unknown): value is Telemetry {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Partial<Telemetry>;
  return (
    typeof v.timestamp === "string" &&
    SLEEP_STATES.includes(v.state as SleepState) &&
    typeof v.vitals === "object" &&
    v.vitals !== null &&
    typeof v.motion_index === "number"
  );
}
