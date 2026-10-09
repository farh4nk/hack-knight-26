import { BABY_NAME } from "./config";
import { unstableHint } from "./cameraHint";
import type { CameraStatus, SleepState } from "./types";

// What the UI shows. "offline" means we aren't hearing from the monitor at all.
export type Tone = "asleep" | "drowsy" | "restless" | "awake" | "unstable" | "offline";

// Mirrors the --tone values in globals.css (used where CSS variables can't reach, e.g. SVG/ribbon).
export const TONE_HEX: Record<Tone, string> = {
  asleep: "#86c5ae",
  drowsy: "#a99bd8",
  restless: "#f0b46a",
  awake: "#ef8a76",
  unstable: "#7d8597",
  offline: "#4b5163",
};

export function toneFor(state: SleepState | null | undefined, offline: boolean): Tone {
  if (offline || !state) return "offline";
  return state === "SIGNAL_UNSTABLE" ? "unstable" : (state.toLowerCase() as Tone);
}

export interface StateCopy {
  headline: string;
  detail: string;
  pill: string;
}

// Wording describes what was observed. Never alarmist, never medical.
export function copyFor(tone: Tone, camera?: CameraStatus): StateCopy {
  const name = BABY_NAME;
  switch (tone) {
    case "asleep":
      return { headline: `${name} is sleeping soundly.`, detail: "Breathing and movement look calm.", pill: "Asleep" };
    case "drowsy":
      return { headline: `${name} is drifting off.`, detail: "Getting sleepy, movement is settling.", pill: "Drowsy" };
    case "restless":
      return { headline: `${name} is stirring.`, detail: "More movement than usual. Auto-soothe is ready if it continues.", pill: "Restless" };
    case "awake":
      return { headline: `${name} is awake.`, detail: "Active and moving around.", pill: "Awake" };
    case "unstable":
      return { headline: `Can’t see ${name} clearly.`, detail: unstableHint(camera), pill: "Signal unclear" };
    case "offline":
      return { headline: "Waiting for the monitor.", detail: "Can’t reach the camera unit right now.", pill: "Offline" };
  }
}

/** Short log line for a transition ("restless" -> "Maya became restless"). */
export function eventText(tone: Tone, camera?: CameraStatus, prev?: Tone | null): string {
  if (prev === "offline" && tone !== "offline") return "Reconnected to the monitor";
  switch (tone) {
    case "asleep": return `${BABY_NAME} settled into sleep`;
    case "drowsy": return `${BABY_NAME} is getting drowsy`;
    case "restless": return `${BABY_NAME} became restless`;
    case "awake": return `${BABY_NAME} woke up`;
    case "unstable": return `Signal unclear: ${unstableHint(camera)}`;
    case "offline": return "Lost connection to the monitor";
  }
}

/** Whether a transition deserves a desktop notification (quiet ones are only logged). */
export function shouldNotify(prev: Tone | null, tone: Tone): boolean {
  if (tone === "restless" || tone === "awake" || tone === "unstable" || tone === "offline") return true;
  return tone === "asleep" && (prev === "restless" || prev === "awake");
}
