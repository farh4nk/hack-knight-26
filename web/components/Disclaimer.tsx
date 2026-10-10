import { APP_NAME } from "@/lib/config";

export function Disclaimer() {
  return (
    <footer className="py-8 text-center text-xs leading-relaxed text-ink-faint">
      {APP_NAME} is an informational wellness monitor, not a medical or SIDS-prevention device.
    </footer>
  );
}
