#!/usr/bin/env bash
# Run ON the Raspberry Pi, from the folder containing compose.yaml.
# Checks prerequisites, finds the Logitech camera among the Pi's many /dev/video* nodes, and
# (with --write) saves what compose needs into .env.
#
#   ./pi_check.sh            report only
#   ./pi_check.sh --write    also write .env (CRADLEECHO_VIDEO_DEVICE, VIDEO_GID, RENDER_GID)
set -uo pipefail

WRITE=0
[[ "${1:-}" == "--write" ]] && WRITE=1
FAILS=0
WARNS=0
ok()   { echo "  ok    $*"; }
warn() { echo "  WARN  $*"; WARNS=$((WARNS + 1)); }
bad()   { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); }

echo "System"
case "$(uname -m)" in
  aarch64|arm64) ok "64-bit ARM ($(uname -m))" ;;
  *) bad "need 64-bit Raspberry Pi OS (uname -m = $(uname -m)); the images are linux/arm64" ;;
esac
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
if   [[ $mem_mb -ge 3500 ]]; then ok "${mem_mb} MB RAM"
elif [[ $mem_mb -ge 1500 ]]; then warn "${mem_mb} MB RAM: workable, but close other apps (4 GB is comfortable)"
else bad "only ${mem_mb} MB RAM detected"; fi

echo "Docker"
if command -v docker >/dev/null 2>&1; then
  ok "$(docker --version)"
  docker info >/dev/null 2>&1 && ok "can talk to the Docker daemon" \
    || bad "can't reach Docker: is it running, and is $USER in the docker group? (sudo usermod -aG docker \$USER, then log out/in)"
  docker compose version >/dev/null 2>&1 && ok "docker compose plugin present" || bad "docker compose plugin missing"
else
  bad "Docker not installed (curl -fsSL https://get.docker.com | sh)"
fi

echo "Camera"
VIDEO_DEV=""
if command -v v4l2-ctl >/dev/null 2>&1; then
  # A block looks like: "C920 HD Pro Webcam (usb-...):" followed by tab-indented /dev/videoN lines.
  block=$(v4l2-ctl --list-devices 2>/dev/null | awk '
    /^[^[:space:]]/ { match_block = ($0 ~ /logitech|uvc|webcam|c9[0-9][0-9]|brio|usb/i) ; next }
    match_block && /\/dev\/video/ { gsub(/[[:space:]]/, ""); print }')
  for dev in $block; do
    # UVC cameras expose a capture node plus a metadata node; only the capture node lists formats.
    if v4l2-ctl -d "$dev" --list-formats 2>/dev/null | grep -q -E "MJPG|YUYV"; then
      VIDEO_DEV="$dev"
      break
    fi
  done
  if [[ -n "$VIDEO_DEV" ]]; then
    ok "USB camera capture node: $VIDEO_DEV"
    if v4l2-ctl -d "$VIDEO_DEV" --get-ctrl=exposure_dynamic_framerate 2>/dev/null | grep -q ": 1"; then
      warn "camera may drop below 25 fps in dim light (Presage needs >= 25). Fix: v4l2-ctl -d $VIDEO_DEV --set-ctrl=exposure_dynamic_framerate=0 (resets when the camera is replugged)"
    fi
  else
    bad "no USB webcam found. Is the Logitech plugged in? Output of v4l2-ctl --list-devices:"
    v4l2-ctl --list-devices 2>&1 | sed 's/^/        /'
  fi
else
  bad "v4l2-ctl missing (sudo apt install v4l-utils)"
fi
[[ -e /dev/dri ]] && ok "/dev/dri present" || warn "/dev/dri missing: compose.yaml maps it for the Presage bridge; remove that line if the bridge doesn't need it"

echo "Compose settings"
VIDEO_GID=$(getent group video | cut -d: -f3)
RENDER_GID=$(getent group render | cut -d: -f3)
AUDIO_GID=$(getent group audio | cut -d: -f3)
[[ -n "$VIDEO_GID" ]] && ok "video group gid $VIDEO_GID" || warn "no 'video' group found"
[[ -n "$RENDER_GID" ]] && ok "render group gid $RENDER_GID" || warn "no 'render' group found (the default 105 will be used)"
[[ -n "$AUDIO_GID" ]] && ok "audio group gid $AUDIO_GID" || warn "no 'audio' group found (the default 29 will be used)"
if [[ -f daemon.env ]] && grep -q '^PRESAGE_API_KEY=.\+' daemon.env; then ok "PRESAGE_API_KEY set in daemon.env"
else warn "PRESAGE_API_KEY missing in daemon.env: the daemon will fall back to MOCK vitals"; fi
if [[ -f analytics.env ]] && grep -q '^TIGER_DATA_CONNECTION_STRING=.\+' analytics.env; then ok "TIGER_DATA_CONNECTION_STRING set in analytics.env"
else warn "TIGER_DATA_CONNECTION_STRING missing in analytics.env: analytics will fall back to SQLite"; fi
if [[ -f web.env ]] && grep -q '^ELEVENLABS_API_KEY=.\+' web.env; then ok "ELEVENLABS_API_KEY set in web.env"
else warn "ELEVENLABS_API_KEY missing in web.env: voice cloning and talk-to-baby will not work"; fi
docker image inspect cradleecho-daemon:latest >/dev/null 2>&1 && ok "daemon image loaded" || bad "daemon image not loaded (run build_and_ship.sh from your laptop)"
docker image inspect cradleecho-analytics:latest >/dev/null 2>&1 && ok "analytics image loaded" || bad "analytics image not loaded (run build_and_ship.sh from your laptop)"
docker image inspect cradleecho-web:latest >/dev/null 2>&1 && ok "web image loaded" || bad "web image not loaded (run build_and_ship.sh from your laptop)"

if [[ $WRITE -eq 1 ]]; then
  {
    [[ -n "$VIDEO_DEV" ]] && echo "CRADLEECHO_VIDEO_DEVICE=$VIDEO_DEV"
    [[ -n "$VIDEO_GID" ]] && echo "VIDEO_GID=$VIDEO_GID"
    [[ -n "$RENDER_GID" ]] && echo "RENDER_GID=$RENDER_GID"
    [[ -n "$AUDIO_GID" ]] && echo "AUDIO_GID=$AUDIO_GID"
  } > .env
  echo "Wrote .env:"; sed 's/^/        /' .env
fi

echo
echo "Open from another device on this network:"
echo "  http://$(hostname | sed "s/\.local$//").local:3000"
for ip in $(hostname -I 2>/dev/null); do echo "  http://$ip:3000"; done
echo
echo "$FAILS failed, $WARNS warnings"
[[ $FAILS -eq 0 ]]
