import { APP_NAME } from "@/lib/config";

export function Disclaimer() {
  return (
    <footer className="py-8 text-center text-xs leading-relaxed text-ink-faint">
      <p>{APP_NAME} is an informational wellness monitor, not a medical or SIDS-prevention device.</p>
      <p className="mt-1 text-[11px] text-ink-faint/80">
        Privacy Guarantee: All video capture and biometric inference are computed 100% locally on-device. Zero crib video is uploaded to the cloud.
      </p>
    </footer>
  );
}
