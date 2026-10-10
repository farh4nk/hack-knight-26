# Where Presage runs (measured 2026-10-10)

**Short version:** a Raspberry Pi 4 cannot feed the Presage bridge 25 fps. Run the daemon (and
Presage) on a laptop and let the Pi be the camera unit. A Pi 5-class board should fit it all in one box.

## What we measured (Pi 4, Logitech Brio 101, `CRADLEECHO_DIAG=1`)
| Setup | Frames reaching the bridge | `kFrameRateTooLow` |
|---|---|---|
| Pi runs everything, 480x360 | 20-27 /s | most of the time |
| Pi, 320x240 (smaller frames do not help) | 23-24 /s | most of the time |
| Pi, + CPU governor `performance`, no browser open, frames written from a thread | 20-25 /s | about half |
| **Mac runs Presage, Pi streams the camera** | **29 /s** | **none** |

On the Pi the bridge's mediapipe threads alone use ~2.5 of 4 cores; the camera, face gate, preview
and the rest of the daemon need the remainder, so the Presage SDK sits right at its 25 fps limit.

## Run it: Pi = camera, Mac = Presage
1. Pi (camera only, no Presage credits spent there):
   `CRADLEECHO_SOURCE=mock CRADLEECHO_STREAM_FPS=30 docker compose up -d --no-deps daemon`
2. Mac (same arm64 image runs natively on Apple Silicon; needs `daemon/.env` with `PRESAGE_API_KEY`):
   ```
   docker run -d --name mac-presage -p 8000:8000 --env-file daemon/.env \
     -e CRADLEECHO_CAMERA=http://<pi-tailscale-ip>:8000/video_feed \
     -e CRADLEECHO_SOURCE=presage \
     -e CRADLEECHO_PRESAGE_CMD="/opt/bridge/bridge --stdin 480x360" \
     -e CRADLEECHO_PRESAGE_FPS=60 -e CRADLEECHO_GATE_CHEST_ROOM=1.0 \
     cradleecho-daemon:latest
   ```
3. Run the web app on the Mac (`cd web && npm run dev`); it talks to `localhost:8000`.
4. Turn the camera on/off from the UI switch (it switches the Pi's camera too only if you point the
   UI at the Pi; the Mac daemon's switch only stops Presage and its view of the stream).

Add `-e CRADLEECHO_DIAG=1` to either side to log pipeline rates every 5 s (`DIAG ...` lines).
Pi tip: `echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` (resets on reboot).

## Still open
- With stable fps Presage now reports `kChestNotVisible`: it wants more of the chest in view
  (camera further back / tilted down). Heart rate needs a steady signal after that.
- The Pi-only mode still works for demos with simulated data.
