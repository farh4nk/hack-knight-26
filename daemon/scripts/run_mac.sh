#!/usr/bin/env bash
# Run the CradleEcho daemon on a Mac.
#
#   scripts/run_mac.sh                 native, mock vitals, uses the Mac webcam directly
#   scripts/run_mac.sh --facegate      native, OpenCV face gate on (fake Presage bridge)
#   scripts/run_mac.sh docker          Docker; host camera is streamed into the container
#   scripts/run_mac.sh docker --presage  Docker with real Presage (needs PRESAGE_API_KEY in .env)
#   scripts/run_mac.sh docker --stamp  also burn capture time into frames, for scripts/measure_latency.py
#   scripts/run_mac.sh stop            stop everything this script started
#
# Native mode needs `uv`; Docker mode needs Docker Desktop (and uv for the camera publisher).
set -euo pipefail

cd "$(dirname "$0")/.."
RUN_DIR=.run
PORT=8000
CAM_PORT=8090
mkdir -p "$RUN_DIR"

MODE=native
FACEGATE=0
PRESAGE=0
STOP=0
STAMP=0
for arg in "$@"; do
  case "$arg" in
    docker) MODE=docker ;;
    stop) STOP=1 ;;
    --facegate) FACEGATE=1 ;;
    --presage) PRESAGE=1 ;;
    --stamp) STAMP=1 ;;
    -h|--help) sed -n 2,12p "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg (try --help)" >&2; exit 2 ;;
  esac
done

listening() { lsof -tiTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

kill_pidfile() {
  local f="$RUN_DIR/$1.pid"
  if [[ -f "$f" ]]; then
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  fi
}

stop_all() {
  kill_pidfile daemon
  kill_pidfile publisher
  if command -v docker >/dev/null 2>&1; then
    docker compose -f compose.mac.yaml down >/dev/null 2>&1 || true
  fi
  echo "Stopped."
}

if [[ $STOP -eq 1 ]]; then
  stop_all
  exit 0
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is required. Install it with: brew install uv" >&2
  exit 1
}

if listening "$PORT"; then
  echo "Port $PORT is already in use. Run: scripts/run_mac.sh stop (or free the port) and retry." >&2
  exit 1
fi

lan_ip() { ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost; }

if [[ "$MODE" == "native" ]]; then
  uv sync --quiet
  if [[ $FACEGATE -eq 1 ]]; then
    export CRADLEECHO_SOURCE=presage
    export PRESAGE_API_KEY="${PRESAGE_API_KEY:-dummy}"
    export CRADLEECHO_PRESAGE_CMD="python3 presage_bridge/fake_bridge.py --stdin 640x480"
  fi
  echo "Daemon (native) on http://$(lan_ip):$PORT   Ctrl+C to stop"
  echo $$ > "$RUN_DIR/daemon.pid" # exec keeps this PID, so `stop` can find the daemon
  exec uv run python -m cradleecho
fi

# ---- docker mode ---------------------------------------------------------
command -v docker >/dev/null 2>&1 || {
  echo "Docker not found. Install Docker Desktop, start it, and retry." >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "Docker is installed but not running. Start Docker Desktop and retry." >&2
  exit 1
}
if listening "$CAM_PORT"; then
  echo "Port $CAM_PORT is already in use (camera publisher). Run: scripts/run_mac.sh stop" >&2
  exit 1
fi

export CRADLEECHO_SOURCE=mock
if [[ $PRESAGE -eq 1 ]]; then
  grep -q '^PRESAGE_API_KEY=.\+' .env 2>/dev/null || {
    echo "--presage needs PRESAGE_API_KEY set in daemon/.env" >&2
    exit 1
  }
  export CRADLEECHO_SOURCE=presage
fi

cleanup() { stop_all; }
trap cleanup EXIT INT TERM

echo "Starting camera publisher on :$CAM_PORT (allow camera access if macOS asks)..."
uv run python scripts/camera_publisher.py --port "$CAM_PORT" $([[ $STAMP -eq 1 ]] && echo --stamp) > "$RUN_DIR/publisher.log" 2>&1 &
echo $! > "$RUN_DIR/publisher.pid"

for _ in $(seq 1 40); do
  curl -sf "http://localhost:$CAM_PORT/healthz" >/dev/null 2>&1 && break
  if ! kill -0 "$(cat "$RUN_DIR/publisher.pid")" 2>/dev/null; then
    echo "Camera publisher failed:" >&2
    cat "$RUN_DIR/publisher.log" >&2
    exit 1
  fi
  sleep 0.5
done

echo "Daemon (docker, source=$CRADLEECHO_SOURCE) on http://$(lan_ip):$PORT   Ctrl+C to stop"
docker compose -f compose.mac.yaml up --build
