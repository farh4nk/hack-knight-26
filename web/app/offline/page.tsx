import { APP_NAME } from "@/lib/config";
import Link from "next/link";

export default function OfflinePage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg-0)] px-6">
      <div className="text-center max-w-sm">
        <svg className="mx-auto h-16 w-16 text-tone/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        <h1 className="mt-6 font-display text-3xl text-ink [font-variation-settings:'SOFT'_100]">
          You&apos;re offline
        </h1>
        <p className="mt-3 text-ink-dim">
          The monitor can&apos;t be reached right now. Check your connection and try again.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-tone px-5 py-3 text-sm font-medium text-[var(--bg-0)] transition hover:opacity-90"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Try again
        </Link>
        <p className="mt-8 text-xs text-ink-faint">
          {APP_NAME} works best online. Biometrics and auto-soothe run locally on the monitor.
        </p>
      </div>
    </div>
  );
}