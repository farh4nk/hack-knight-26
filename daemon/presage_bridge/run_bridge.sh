#!/usr/bin/env bash
set -euo pipefail

DEV="${PRESAGE_VIDEO_DEVICE:-/dev/video11}"
ARGS=("--rm" "-i" "--init" "--device" "$DEV")

if [[ -n "${PRESAGE_API_KEY:-}" ]]; then
    ARGS+=("-e" "PRESAGE_API_KEY")
fi

if [[ -n "${PRESAGE_VIDEO_DEVICE:-}" ]]; then
    ARGS+=("-e" "PRESAGE_VIDEO_DEVICE")
fi

exec docker run "${ARGS[@]}" cradleecho-presage-bridge
