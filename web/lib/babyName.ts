"use client";

import { useSyncExternalStore } from "react";

// The baby's name, stored in this browser (localStorage). Optional: unnamed copy says "your baby".
const NAME_KEY = "cradleecho.babyName";
const DISMISSED_KEY = "cradleecho.babyNamePromptDismissed";
export const MAX_NAME_LENGTH = 30;

let loaded = false;
let name = "";
let promptDismissed = false;
const listeners = new Set<() => void>();

/** Trim, collapse runs of whitespace, and cap the length. */
export function cleanName(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().slice(0, MAX_NAME_LENGTH);
}

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    name = cleanName(localStorage.getItem(NAME_KEY) ?? "");
    promptDismissed = localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    /* storage unavailable: keep defaults */
  }
}

function persist() {
  try {
    if (name) localStorage.setItem(NAME_KEY, name);
    else localStorage.removeItem(NAME_KEY);
    localStorage.setItem(DISMISSED_KEY, promptDismissed ? "1" : "0");
  } catch {
    /* storage unavailable */
  }
}

const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => listeners.delete(cb);
};
const emit = () => listeners.forEach((l) => l());

/** Name for titles and API calls: the saved name, or "Baby". */
export const babyTitle = (n: string) => n || "Baby";
/** Name at the start of a sentence: the saved name, or "Your baby". */
export const babySubject = (n: string) => n || "Your baby";
/** Name for the middle of a sentence: the saved name, or "your baby". */
export const babyObject = (n: string) => n || "your baby";

/** Current name ("" = not set). Safe to call from event handlers and effects. */
export function getBabyName(): string {
  load();
  return name;
}

/** Save the name (empty clears it). Also stops the first-run prompt from reappearing. */
export function setBabyName(raw: string): void {
  load();
  name = cleanName(raw);
  promptDismissed = true;
  persist();
  emit();
}

export function dismissNamePrompt(): void {
  load();
  promptDismissed = true;
  persist();
  emit();
}

/**
 * The baby's name for rendering. null on the server and during hydration, so callers can wait for
 * the real value (and avoid doing work, like rendering voice phrases, with a placeholder).
 */
export function useBabyName(): string | null {
  return useSyncExternalStore(subscribe, getBabyName, () => null);
}

export function useNamePromptDismissed(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => {
      load();
      return promptDismissed;
    },
    () => true, // never flash the prompt before the stored value is known
  );
}
