#!/usr/bin/env bash
# Build the daemon + analytics + web images for the Pi (linux/arm64) on THIS machine and load them on the Pi.
# The Pi never builds anything: compiling the Presage bridge or running `next build` on a Pi 4
# is slow and can run out of memory.
#
#   deploy/pi/build_and_ship.sh pi@raspberrypi.local              # images + compose file
#   deploy/pi/build_and_ship.sh pi@raspberrypi.local --with-env   # also copy API keys (Presage, Tiger Data, Gemini, ElevenLabs)
#
# On an Apple Silicon Mac the arm64 build is native and fast. On x86 machines run once:
#   docker run --privileged --rm tonistiigi/binfmt --install arm64
set -euo pipefail

TARGET="${1:-}"
WITH_ENV=0
[[ "${2:-}" == "--with-env" ]] && WITH_ENV=1
[[ -n "$TARGET" ]] || { sed -n 2,9p "$0"; exit 2; }

cd "$(dirname "$0")/../.."
REMOTE_DIR='~/cradleecho'

command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker isn't running" >&2; exit 1; }
ssh -o BatchMode=yes -o ConnectTimeout=8 "$TARGET" true 2>/dev/null || {
  echo "Can't ssh to $TARGET without a prompt. Check the host name and your ssh key (ssh-copy-id)." >&2
  exit 1
}

echo "==> Building daemon (linux/arm64)"
docker buildx build --platform linux/arm64 --load -t cradleecho-daemon:latest daemon
echo "==> Building analytics (linux/arm64)"
docker buildx build --platform linux/arm64 --load -t cradleecho-analytics:latest -f backend/Dockerfile .
echo "==> Building web (linux/arm64)"
docker buildx build --platform linux/arm64 --load -t cradleecho-web:latest web

echo "==> Pulling Caddy (linux/arm64)"
docker pull --platform linux/arm64 caddy:2

echo "==> Shipping images to $TARGET (compressed; a few minutes the first time)"
docker save cradleecho-daemon:latest cradleecho-analytics:latest cradleecho-web:latest caddy:2 | gzip | ssh "$TARGET" 'gunzip | docker load'

echo "==> Copying compose file, Caddyfile, pairing page, and check script"
ssh "$TARGET" "mkdir -p $REMOTE_DIR"
scp -q deploy/pi/compose.yaml deploy/pi/Caddyfile deploy/pi/pi_check.sh "$TARGET:$REMOTE_DIR/"
scp -rq deploy/pi/pair "$TARGET:$REMOTE_DIR/"
ssh "$TARGET" "chmod +x $REMOTE_DIR/pi_check.sh"

if [[ $WITH_ENV -eq 1 ]]; then
  [[ -f daemon/.env ]] || { echo "daemon/.env not found" >&2; exit 1; }
  scp -q daemon/.env "$TARGET:$REMOTE_DIR/daemon.env"

  # Analytics env: TIGER_DATA_CONNECTION_STRING & GEMINI_API_KEY
  BACKEND_ENV=""
  for f in .env backend/.env; do [[ -f "$f" ]] && BACKEND_ENV="$f" && break; done
  if [[ -n "$BACKEND_ENV" ]]; then
    scp -q "$BACKEND_ENV" "$TARGET:$REMOTE_DIR/analytics.env"
    echo "Copied $BACKEND_ENV -> analytics.env"
  else
    ssh "$TARGET" "touch $REMOTE_DIR/analytics.env"
  fi

  # Only the ElevenLabs key goes to the Pi; the rest of web/.env.local is dev-only settings.
  ENV_FILE=""
  for f in web/.env.local web/.env; do [[ -f "$f" ]] && ENV_FILE="$f" && break; done
  EL_LINE=""
  [[ -n "$ENV_FILE" ]] && EL_LINE=$(grep -E '^ELEVENLABS_API_KEY=.+' "$ENV_FILE" | grep -v 'your_' | head -1 || true)
  printf '%s\n' "$EL_LINE" | ssh "$TARGET" "cat > $REMOTE_DIR/web.env"
  ssh "$TARGET" "chmod 600 $REMOTE_DIR/daemon.env $REMOTE_DIR/analytics.env $REMOTE_DIR/web.env"
  echo "Copied daemon/.env -> daemon.env"
  [[ -n "$EL_LINE" ]] && echo "Copied ELEVENLABS_API_KEY -> web.env" || echo "NOTE: no ELEVENLABS_API_KEY in web/.env.local; voice features will not work on the Pi."
else
  ssh "$TARGET" "cd $REMOTE_DIR && touch daemon.env analytics.env web.env"
  echo "NOTE: daemon.env, analytics.env, and web.env on the Pi are empty. Add API keys or re-run with --with-env."
fi

cat <<DONE

Done. On the Pi:
  cd ~/cradleecho
  ./pi_check.sh --write     # finds the Logitech, checks prerequisites, writes .env (includes SITE_HOST)
  docker compose up -d
Then open https://<pi-host>.local/ from your laptop (pair first at http://<pi-host>.local/pair).
DONE