# Running CradleEcho on the Raspberry Pi

The Pi runs everything: camera capture, Presage, sleep-state logic, and the web UI. Your laptop is
only a browser: open `http://<pi-host>:3000` to watch the feed and see notifications.

```
Logitech webcam ──USB──▶ Pi 4: [daemon :8000] ──speaker──▶ Crib audio
                               [analytics :8001]
                               [web UI :3000]
                                     ▲
                                     └── laptop/phone browser (same network)
```

## Requirements
- Raspberry Pi 4, **64-bit** Raspberry Pi OS (Lite is fine), 4 GB RAM recommended (2 GB is tight).
- Docker + the compose plugin: `curl -fsSL https://get.docker.com | sh`, then `sudo usermod -aG docker $USER` and log back in.
- `sudo apt install v4l-utils` (lets `pi_check.sh` find the camera).
- SSH access from your laptop (`ssh-copy-id pi@<pi-host>`), a `PRESAGE_API_KEY` in `daemon/.env`, database keys in `.env`, and an `ELEVENLABS_API_KEY` in `web/.env.local`.

## Deploy (laptop → Pi)
The Pi builds nothing. Compiling the Presage bridge or `next build` on a Pi 4 is slow and can run out of memory.

```bash
# on your laptop, from the repo root (Docker running)
deploy/pi/build_and_ship.sh pi@raspberrypi.local --with-env
```
This builds both images for `linux/arm64`, loads them on the Pi, and copies `compose.yaml`, `pi_check.sh`
and (with `--with-env`) your Presage key (`daemon.env`) and ElevenLabs key (`web.env`). The daemon image is ~2.2 GB, so the first transfer takes a few minutes.
On an Apple Silicon Mac the arm64 build is native. On an x86 machine run once:
`docker run --privileged --rm tonistiigi/binfmt --install arm64`.

## Start (on the Pi)
```bash
cd ~/cradleecho
./pi_check.sh --write     # checks everything, finds the Logitech, writes .env
docker compose up -d
```
Then open `http://<pi-host>:3000` from your laptop (`pi_check.sh` prints the exact addresses).
Stop with `docker compose down`; logs with `docker compose logs -f daemon`.

## Verified vs not yet verified
Verified (on an arm64 machine, no Pi hardware):
- Both images build for `linux/arm64`, including the C++ Presage bridge against the arm64 SDK package.
- The bridge binary starts with no missing libraries; the full stack runs and the UI works when opened
  by IP address from another device (it talks to the daemon on the host that served the page).
- `pi_check.sh` picks the right camera node from realistic `v4l2-ctl` output.

**Not verified: needs a real Pi + Logitech.** Real Presage vitals on the Pi, Pi 4 CPU load
(Presage + face gate + JPEG encoding), `/dev/dri` passthrough, and the Logitech's actual node and formats.

## Troubleshooting
- **"Camera offline" / synthetic feed:** run `./pi_check.sh`. A Pi has many `/dev/video*` nodes and the
  Logitech may not be `video0`. `--write` stores the right one in `.env`.
- **Daemon unhealthy / mock vitals:** `docker compose logs daemon`. `/healthz` shows `"source":"mock"` when the API key is missing.
- **Voice recording blocked:** browsers only allow the microphone on `localhost` or HTTPS, so recording a voice sample
  over plain `http://<pi-host>:3000` fails. Options: record the sample on the Pi itself, put the Pi behind
  HTTPS (e.g. Tailscale Serve), or for a demo only, allow the origin in `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
- **Can't reach the Pi from the laptop:** same network? Some venue Wi-Fi isolates devices from each other;
  use a phone hotspot or a direct Ethernet cable.

## Open decisions
- **Where does soothing audio play?** The current auto-soothe engine plays audio in the browser tab, so with the
  Pi as the brain the sound would come out of the laptop, not the nursery. Playing from the Pi (a speaker on the Pi)
  means moving that logic into the daemon.
- **Notifications** to the laptop are shown while the page is open. Notifications with the tab closed need a push
  service (e.g. ntfy) called from the daemon.
