// Shared sleep states and default soothing phrases (Dev 3)

export const SLEEP_STATES = [
  "ASLEEP",
  "DROWSY",
  "RESTLESS",
  "AWAKE",
  "SIGNAL_UNSTABLE",
] as const;

export type SleepState = (typeof SLEEP_STATES)[number];

/** The soothing phrases spoken in the parent's cloned voice; the first one uses the baby's name if set. */
export function soothingPhrases(name: string): string[] {
  return [
    name ? `Shh, you’re safe, go back to sleep ${name}.` : "Shh, you’re safe, go back to sleep.",
    "Mommy and daddy are right here, sweet dreams.",
    "Everything is okay, close your eyes.",
  ];
}
