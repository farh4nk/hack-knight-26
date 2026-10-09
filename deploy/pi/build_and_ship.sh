#!/usr/bin/env bash
# Build the daemon + web images for the Pi (linux/arm64) on THIS machine and load them on the Pi.
# The Pi never builds anything: compiling the Presage bridge or running `next build` on a Pi 4
# is slow and can run out of memory.
#
#   deploy/pi/build_and_ship.sh pi@raspberrypi.local              # images + compose file
#   deploy/pi/build_and_ship.sh pi@raspberrypi.local --with-env   # also copy daemon/.env (API key)
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
echo "==> Building web (linux/arm64)"
docker buildx build --platform linux/arm64 --load -t cradleecho-web:latest web

echo "==> Shipping images to $TARGET (compressed; a few minutes the first time)"
docker save cradleecho-daemon:latest cradleecho-web:latest | gzip | ssh "$TARGET" 'gunzip | docker load'

echo "==> Copying compose file and check script"
ssh "$TARGET" "mkdir -p $REMOTE_DIR"
scp -q deploy/pi/compose.yaml deploy/pi/pi_check.sh "$TARGET:$REMOTE_DIR/"
ssh "$TARGET" "chmod +x $REMOTE_DIR/pi_check.sh"

if [[ $WITH_ENV -eq 1 ]]; then
  [[ -f daemon/.env ]] || { echo "daemon/.env not found" >&2; exit 1; }
  scp -q daemon/.env "$TARGET:$REMOTE_DIR/daemon.env"
  ssh "$TARGET" "chmod 600 $REMOTE_DIR/daemon.env"
  echo "Copied daemon/.env -> $REMOTE_DIR/daemon.env"
else
  ssh "$TARGET" "touch $REMOTE_DIR/daemon.env"
  echo "NOTE: $REMOTE_DIR/daemon.env on the Pi is empty. Add PRESAGE_API_KEY=... or re-run with --with-env."
fi

cat <<DONE

Done. On the Pi:
  cd ~/cradleecho
  ./pi_check.sh --write     # finds the Logitech, checks prerequisites, writes .env
  docker compose up -d
Then open http://<pi-host>:3000 from your laptop.
DONE
