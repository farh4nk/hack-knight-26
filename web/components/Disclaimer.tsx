import { APP_NAME } from "@/lib/config";

export function Disclaimer() {
  return (
    <footer className="border-t border-white/10 py-6 text-center text-sm text-slate-500">
      {APP_NAME} is an informational wellness monitor, not a medical or SIDS-prevention device.
    </footer>
  );
}
