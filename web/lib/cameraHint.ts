import type { CameraFraming, CameraStatus } from "./types";

// Observed framing problems, phrased as what to fix (never as a risk to the baby).
const FRAMING_HINTS: Partial<Record<CameraFraming, string>> = {
  NO_FACE: "No face in view — check the camera angle",
  MULTIPLE_FACES: "More than one face in view",
  TOO_SMALL: "Too far away — move the camera closer",
  OFF_CENTER: "Off-center — re-aim the camera",
  NO_CHEST_ROOM: "Chest not visible — tilt the camera down",
};

export const DEFAULT_UNSTABLE_HINT = "Adjust Crib Lighting";

/** Best available fix for a SIGNAL_UNSTABLE reading: Presage hint, then framing, then lighting. */
export function unstableHint(camera: CameraStatus | undefined): string {
  if (!camera) return DEFAULT_UNSTABLE_HINT;
  if (camera.sdk_hint) return camera.sdk_hint;
  return FRAMING_HINTS[camera.framing] ?? DEFAULT_UNSTABLE_HINT;
}

export const FRAMING_LABELS: Record<CameraFraming, string> = {
  OK: "Framing OK",
  NO_FACE: "No face",
  MULTIPLE_FACES: "Multiple faces",
  TOO_SMALL: "Too far",
  OFF_CENTER: "Off-center",
  NO_CHEST_ROOM: "No chest room",
  UNKNOWN: "Framing unknown",
};
