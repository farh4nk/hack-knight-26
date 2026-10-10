"use client";

import { dismissNamePrompt, useBabyName, useNamePromptDismissed } from "@/lib/babyName";
import { BabyNameForm } from "./BabyNameForm";

/** First-run nudge to name the baby. Goes away once a name is saved or the user says "Not now". */
export function NamePrompt() {
  const name = useBabyName();
  const dismissed = useNamePromptDismissed();
  if (name === null || name !== "" || dismissed) return null;

  return (
    <section aria-label="Baby's name" className="rise mt-7 max-w-xl rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
      <h2 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">What’s your baby’s name?</h2>
      <p className="mt-1.5 text-sm text-ink-dim">
        It personalizes alerts and the soothing phrases spoken in your voice. You can change it any time.
      </p>
      <div className="mt-4">
        <BabyNameForm autoFocus submitLabel="Save name" />
      </div>
      <button
        type="button"
        onClick={dismissNamePrompt}
        className="mt-3 text-sm text-ink-faint underline underline-offset-4 transition hover:text-ink"
      >
        Not now
      </button>
    </section>
  );
}
