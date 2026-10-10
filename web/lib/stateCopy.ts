import { unstableHint } from "./cameraHint";
import type { CameraStatus, SleepState, Telemetry } from "./types";

// What the UI shows. "offline" = we aren't hearing from the monitor at all; "paused" = the user
// switched the camera off.
export type Tone = "asleep" | "drowsy" | "restless" | "awake" | "unstable" | "offline" | "paused";

// Mirrors the --tone values in globals.css (used where CSS variables can't reach, e.g. SVG/ribbon).
export const TONE_HEX: Record<Tone, string> = {
  asleep: "#86c5ae",
  drowsy: "#a99bd8",
  restless: "#f0b46a",
  awake: "#ef8a76",
  unstable: "#7d8597",
  offline: "#4b5163",
  paused: "#8a8f9c",
};

export function toneFor(
  state: SleepState | null | undefined,
  offline: boolean,
  cameraEnabled: boolean | undefined = true,
  mode?: "SIMULATED" | "REALTIME",
): Tone {
  if (offline || !state) return "offline";
  if (cameraEnabled === false && mode !== "SIMULATED") return "paused";
  return state === "SIGNAL_UNSTABLE" ? "unstable" : (state.toLowerCase() as Tone);
}

/** Tone for a telemetry packet (accounts for the camera switch and simulation mode). */
export function toneOf(
  t: Telemetry | null | undefined,
  offline: boolean,
  fallbackMode?: "SIMULATED" | "REALTIME",
): Tone {
  const mode = t?.mode ?? fallbackMode;
  return toneFor(t?.state, offline || !t, t?.camera?.enabled, mode);
}

// The baby's name is optional. Unnamed copy says "your baby" ("Your baby is sleeping soundly.").
const subject = (name: string) => name || "Your baby";
const object = (name: string) => name || "your baby";

export interface StateCopy {
  headline: string;
  detail: string;
  pill: string;
}

// Wording describes what was observed. Never alarmist, never medical.
export function copyFor(tone: Tone, camera?: CameraStatus, name = ""): StateCopy {
  switch (tone) {
    case "asleep":
      return { headline: `${subject(name)} is sleeping soundly.`, detail: "Breathing and movement look calm.", pill: "Asleep" };
    case "drowsy":
      return { headline: `${subject(name)} is drifting off.`, detail: "Settling: breathing is in a sleeping range and movement is calm.", pill: "Drowsy" };
    case "restless":
      return { headline: `${subject(name)} is stirring.`, detail: "More movement than usual. Auto-soothe is ready if it continues.", pill: "Restless" };
    case "awake":
      return { headline: `${subject(name)} is awake.`, detail: "Active, or breathing faster than in sleep.", pill: "Awake" };
    case "unstable":
      return { headline: `Can’t see ${object(name)} clearly.`, detail: unstableHint(camera), pill: "Signal unclear" };
    case "paused":
      return {
        headline: "Monitoring is paused.",
        detail: "The camera is off. Turn it on to resume. No Presage credits are being used.",
        pill: "Camera off",
      };
    case "offline":
      return { headline: "Waiting for the monitor.", detail: "Can’t reach the camera unit right now.", pill: "Offline" };
  }
}

/** Short log line for a transition ("restless" -> "Maya became restless"). */
export function eventText(tone: Tone, camera?: CameraStatus, prev?: Tone | null, name = ""): string {
  if (tone === "paused") return "Camera turned off";
  if (prev === "paused") return "Camera turned on";
  if (prev === "offline" && tone !== "offline") return "Reconnected to the monitor";
  const who = subject(name);
  switch (tone) {
    case "asleep": return `${who} settled into sleep`;
    case "drowsy": return `${who} is getting drowsy`;
    case "restless": return `${who} became restless`;
    case "awake": return `${who} woke up`;
    case "unstable": return `Signal unclear: ${unstableHint(camera)}`;
    case "offline": return "Lost connection to the monitor";
  }
}

/** Whether a transition deserves a desktop notification (quiet ones are only logged). */
export function shouldNotify(prev: Tone | null, tone: Tone): boolean {
  if (tone === "restless" || tone === "awake" || tone === "unstable" || tone === "offline") return true;
  return tone === "asleep" && (prev === "restless" || prev === "awake");
}
