// Shared sleep states and default soothing phrases (Dev 3)

export const SLEEP_STATES = [
  "ASLEEP",
  "DROWSY",
  "RESTLESS",
  "AWAKE",
  "SIGNAL_UNSTABLE",
] as const;

export type SleepState = (typeof SLEEP_STATES)[number];

export const SOOTHING_PHRASES = [
  "Shh, you’re safe, go back to sleep Maya.",
  "Mommy and daddy are right here, sweet dreams.",
  "Everything is okay, close your eyes.",
];
