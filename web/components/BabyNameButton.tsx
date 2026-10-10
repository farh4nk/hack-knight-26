"use client";

import { useState } from "react";
import { setBabyName, useBabyName } from "@/lib/babyName";
import { BabyNameForm } from "./BabyNameForm";

/** Header control: shows the baby's name and opens a small editor. */
export function BabyNameButton() {
  const name = useBabyName();
  const [open, setOpen] = useState(false);
  if (name === null) return <span className="h-8 w-24" aria-hidden />; // reserve space; no flash

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="flex items-center gap-1.5 rounded-full px-3 py-1 text-sm text-ink-dim ring-1 ring-white/12 transition hover:text-ink"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
        {name || "Add baby’s name"}
      </button>

      {open && (
        <>
          <button type="button" aria-label="Close" className="fixed inset-0 z-10 cursor-default" onClick={() => setOpen(false)} />
          <div
            role="dialog"
            aria-label="Baby's name"
            className="absolute right-0 z-20 mt-2 w-72 rounded-2xl bg-[#14131f] p-4 shadow-2xl ring-1 ring-white/12"
          >
            <p className="mb-3 text-sm text-ink-dim">Baby’s name</p>
            <BabyNameForm initial={name} autoFocus onDone={() => setOpen(false)} />
            {name && (
              <button
                type="button"
                onClick={() => {
                  setBabyName("");
                  setOpen(false);
                }}
                className="mt-3 text-xs text-ink-faint underline underline-offset-4 transition hover:text-ink"
              >
                Remove name
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
