#!/usr/bin/env bash
set -euo pipefail

# camera_fanout.sh
# Fans out a single physical V4L2 camera (/dev/video0) into two virtual
# loopback devices (/dev/video10 for OpenCV daemon, /dev/video11 for Presage SDK)
# using v4l2loopback and ffmpeg tee.
#
# DO NOT execute automatically during build or tests. Run manually with sudo when needed.

INPUT_DEVICE="${1:-/dev/video0}"
OUT1="/dev/video10"
OUT2="/dev/video11"

echo "=== CradleEcho Camera Fan-out Setup ==="
echo "Input device: ${INPUT_DEVICE}"
echo "Loopback output 1 (OpenCV):  ${OUT1}"
echo "Loopback output 2 (Presage): ${OUT2}"

# 1. Load v4l2loopback module with two virtual devices
echo "Loading v4l2loopback kernel module..."
sudo modprobe -r v4l2loopback 2>/dev/null || true
sudo modprobe v4l2loopback devices=2 video_nr=10,11 card_label="cradle_cv,cradle_presage" exclusive_caps=1

# 2. Check if output nodes were created
if [[ ! -e "${OUT1}" ]] || [[ ! -e "${OUT2}" ]]; then
    echo "Error: Virtual devices ${OUT1} and ${OUT2} not found. Check v4l2loopback installation."
    exit 1
fi

echo "Virtual devices ready."
echo "Starting ffmpeg tee stream (Press Ctrl+C to terminate)..."

# 3. Stream input device to both virtual outputs
exec ffmpeg -hide_banner -loglevel warning \
    -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i "${INPUT_DEVICE}" \
    -codec copy -f v4l2 "${OUT1}" \
    -codec copy -f v4l2 "${OUT2}"
