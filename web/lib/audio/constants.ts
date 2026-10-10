// Shared sleep states and default soothing phrases (Dev 3)

export const SLEEP_STATES = [
  "ASLEEP",
  "DROWSY",
  "RESTLESS",
  "AWAKE",
  "SIGNAL_UNSTABLE",
] as const;

export type SleepState = (typeof SLEEP_STATES)[number];

/** Short soothing phrases spoken in the parent's cloned voice, softly and gently. */
export function soothingPhrases(): string[] {
  return ["Shhh...", "Go to sleep...", "Good night..."];
}
