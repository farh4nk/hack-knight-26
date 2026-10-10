"use client";

import { useState } from "react";
import { MAX_NAME_LENGTH, cleanName, setBabyName } from "@/lib/babyName";

interface BabyNameFormProps {
  initial?: string;
  autoFocus?: boolean;
  /** Called after saving, or when the user cancels with Escape. */
  onDone?: () => void;
  submitLabel?: string;
}

export function BabyNameForm({ initial = "", autoFocus, onDone, submitLabel = "Save" }: BabyNameFormProps) {
  const [value, setValue] = useState(initial);
  const clean = cleanName(value);

  const save = () => {
    setBabyName(clean);
    onDone?.();
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="flex gap-2"
    >
      <label htmlFor="baby-name" className="sr-only">
        Baby’s name
      </label>
      <input
        id="baby-name"
        type="text"
        value={value}
        autoFocus={autoFocus}
        maxLength={MAX_NAME_LENGTH}
        autoComplete="off"
        placeholder="Baby’s name"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onDone?.()}
        className="min-w-0 flex-1 rounded-xl bg-white/5 px-3.5 py-2 text-sm text-ink placeholder:text-ink-faint ring-1 ring-white/10 focus:outline-none focus:ring-tone/50"
      />
      <button
        type="submit"
        disabled={clean === initial}
        className="rounded-xl bg-ink px-4 py-2 text-sm font-medium text-[#0a0b15] transition hover:opacity-90 disabled:opacity-40"
      >
        {submitLabel}
      </button>
    </form>
  );
}
