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

## Tuning on a Pi 4 (measured on a Pi 4 + Logitech Brio 101)
The defaults in `compose.yaml` come from real measurements; override any of them in the Pi's `.env`.

| Setting | Default | Why |
|---|---|---|
| `PRESAGE_FRAME_SIZE` | `480x360` | The Presage bridge processes ~14 fps at 640x480 but ~27 fps at 480x360. Presage needs >= 25 fps. |
| `GATE_CHEST_ROOM` | `1.0` | The daemon's face gate wants this many face-heights of empty space below the chin. The code default (1.75) forces a very specific seating position. |
| `PRESAGE_FPS` | `60` | Presage's own frame throttle equals the camera rate (30), so timing jitter drops frames. 60 disables the throttle. |

**What the logs mean** (`docker compose logs -f daemon`, lines starting `SDK validation:`):
- `kOk: Hold still and record.` Presage is reading you. Real numbers appear after a short warm-up (breathing ramps up over ~30 s).
- `kChestNotVisible` / `kFaceNotForward` / `kExcessiveMotion` / `kNoFaceFound`: reposition; these are Presage's own requirements, not bugs.
- `kFrameRateTooLow`: the stream is under 25 fps. Check `./pi_check.sh` and lighting (below).

**Frame rate.** The daemon must deliver >= 25 fps. Two things can break that:
- Webcams lower their frame rate in dim light. Turn it off with
  `v4l2-ctl -d /dev/video0 --set-ctrl=exposure_dynamic_framerate=0` (resets when the camera is replugged; `pi_check.sh` warns if it is on).
- Never set `CAP_PROP_BUFFERSIZE=1` on a V4L2 camera: with one buffer the driver can't capture while a frame is read, which halved the rate from 30 to 15 fps here. A regression test covers it.

**A Pi 4 is at its limit for Presage.** Measured with `CRADLEECHO_DIAG=1`: the bridge's mediapipe threads use ~2.5 of 4 cores and only 20-25 fps reach it (below the 25 it needs), even at 320x240, with the `performance` CPU governor and no browser open. The camera itself delivers a steady 30 fps and the face gate costs ~6 ms/frame. With Presage on a Mac reading the Pi's stream, 29 fps reached the bridge with no `kFrameRateTooLow`. See [presage-compute.md](presage-compute.md) for the table and the Pi-as-camera setup (`CRADLEECHO_SOURCE=mock CRADLEECHO_STREAM_FPS=30`).

## Verified vs not yet verified
Verified (on an arm64 machine, no Pi hardware):
- Both images build for `linux/arm64`, including the C++ Presage bridge against the arm64 SDK package.
- The bridge binary starts with no missing libraries; the full stack runs and the UI works when opened
  by IP address from another device (it talks to the daemon on the host that served the page).
- `pi_check.sh` picks the right camera node from realistic `v4l2-ctl` output.

**Not verified: needs a real Pi + Logitech.** Real Presage vitals on the Pi, Pi 4 CPU load
(Presage + face gate + JPEG encoding), `/dev/dri` passthrough, and the Logitech's actual node and formats.

## Troubleshooting
- **Every request to `hack-knight.local` takes ~5 s (page load 5 s, live data 10 s):** your phone hotspot is
  IPv6-only. macOS then never takes an IPv4 address (check `ipconfig getifaddr en0`: empty, or `192.0.0.2` from
  `ifconfig en0`), and each `.local` lookup waits 5 s for an IPv4 answer that cannot come. Skip the lookup:
  run `deploy/pi/find_pi.sh` on your laptop. It finds the Pi by IPv6 neighbor discovery and prints instant URLs
  (`http://[<ipv6>]:3000`, measured 0.14 s vs 5.1 s). `deploy/pi/find_pi.sh --ssh-config hack-knight.local` also makes
  `ssh pi@hack-knight.local` use the Pi's permanent link-local address (undo with `--remove-ssh-config`). The global
  address changes if the hotspot reconnects; just re-run the script. A hotspot that gives IPv4 (or Ethernet) avoids this.
- **Presage keeps saying `kFrameRateTooLow`:** see "Tuning on a Pi 4" above.
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
