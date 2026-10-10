"""CradleEcho Edge Daemon FastAPI application."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier
from cradleecho.config import settings
from cradleecho.sources.base import VitalsSource
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.audio import edge_player
from cradleecho.sources.presage import PresageVitalsSource
from cradleecho.telemetry import TelemetryHub
from cradleecho.talkback import TalkbackManager, handle_talkback_ws, TalkbackConfig
from cradleecho.listen import ListenHub, handle_listen_ws, ListenConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cradleecho")


class SimulateRestlessRequest(BaseModel):
    seconds: float = Field(default=15.0, ge=1.0, le=300.0)


class CameraToggleRequest(BaseModel):
    enabled: bool


class PlaySootheRequest(BaseModel):
    audio_base64: str | None = None
    phrase: str | None = None


class NightVisionModeRequest(BaseModel):
    mode: str = Field(pattern="^(OFF|AUTO|ON)$")


def build_source() -> VitalsSource:
    source_type = settings.source.lower()
    if source_type == "presage":
        if not settings.presage_api_key:
            logger.warning("PRESAGE_API_KEY is missing; falling back to MockVitalsSource")
            return MockVitalsSource()
        logger.info("Initializing Presage source")
        return PresageVitalsSource()
    logger.info("Initializing Mock vitals source")
    return MockVitalsSource()


KEEPALIVE_S = 1.0  # resend the current frame this often if the camera is idle/synthetic


async def _stream_new_frames(
    request: Request, cam: Camera, get_bytes, limit: int | None
) -> AsyncGenerator[bytes, None]:
    """Yield MJPEG parts, sending each new frame the moment it exists.

    Replaces a fixed 40 ms poll: that added up to 40 ms per frame and re-sent duplicates.
    """
    count = 0
    last_seq = -1
    last_sent = 0.0
    last_disconnect_check = 0.0
    while True:
        now = time.monotonic()
        # `limit` is test-only; is_disconnected() can block under TestClient
        if limit is None and now - last_disconnect_check > 0.25:
            last_disconnect_check = now
            if await request.is_disconnected():
                return
        seq = cam.get_frame_seq()
        if seq != last_seq or now - last_sent >= KEEPALIVE_S:
            last_seq, last_sent = seq, now
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + get_bytes() + b"\r\n"
            count += 1
            if limit is not None and count >= limit:
                return
        else:
            await asyncio.sleep(0.005)


class SetSourceRequest(BaseModel):
    source: str = Field(description="'mock' / 'simulated' for realistic test loop, or 'real' / 'presage' for live optical sensor")


def create_app(
    camera: Camera | None = None,
    source: VitalsSource | None = None,
    classifier: SleepStateClassifier | None = None,
    talkback_manager: TalkbackManager | None = None,
    listen_hub: ListenHub | None = None,
) -> FastAPI:
    cam = camera or Camera()
    clsf = classifier or SleepStateClassifier()

    # Maintain instances of both mock and real sensor sources for seamless runtime switching
    mock_src = MockVitalsSource()
    presage_src = PresageVitalsSource()
    gate = None

    if settings.face_gate:
        from cradleecho.facegate import FaceGate
        gate = FaceGate(
            chest_room=settings.gate_chest_room,
            min_face_frac=settings.gate_min_face_frac,
        )
        presage_src.set_gate(gate)
    cam.add_frame_listener(presage_src.push_frame)

    if source is not None:
        initial_src = source
    elif settings.source.lower() == "presage" and settings.presage_api_key:
        initial_src = presage_src
    else:
        initial_src = mock_src

    hub = TelemetryHub(cam, initial_src, clsf, interval_s=0.5)

    # Talkback & Listen
    tb_manager = talkback_manager or TalkbackManager()
    lh = listen_hub or ListenHub()

    from cradleecho.overlay import draw_vitals_panel
    def _composite_overlay(frame):
        if gate is not None and not isinstance(hub.source, MockVitalsSource):
            gate.draw_overlay(frame)
        active_src = hub.source
        hint = getattr(active_src, 'validation_hint', '')
        session_running = active_src.session_running if isinstance(active_src, PresageVitalsSource) else None
        draw_vitals_panel(
            frame,
            hub.get_latest_payload(),
            sdk_hint=hint,
            session_running=session_running,
        )
    cam.set_overlay(_composite_overlay)

    def sync_presage_pause() -> None:
        """Presage (the paid SDK session) may only run when the camera is on AND the real sensor
        source is selected. Otherwise it would keep consuming camera frames, and credits, while
        the app shows simulated data or the user has switched the camera off."""
        presage_src.set_paused(not cam.is_enabled() or isinstance(hub.source, MockVitalsSource))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting CradleEcho daemon services...")
        cam.start()
        await mock_src.start()
        await presage_src.start()
        sync_presage_pause()
        await hub.start()
        # Start listen hub if enabled
        if lh.enabled:
            await lh.subscribe()  # dummy subscribe to trigger recorder start
            # immediately unsubscribe to keep it running but with 0 subscribers
            # Actually, we just need to ensure the recorder can start on first real subscriber
            pass
        yield
        logger.info("Shutting down CradleEcho daemon services...")
        await hub.stop()
        await presage_src.stop()
        await mock_src.stop()
        cam.stop()
        await lh.stop()

    app = FastAPI(title="CradleEcho Edge Daemon", lifespan=lifespan)

    # CORS configuration
    origins = [orig.strip() for orig in settings.cors_origins.split(",") if orig.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # State handles attached to app.state for testing & introspection
    app.state.camera = cam
    app.state.mock_source = mock_src
    app.state.presage_source = presage_src
    app.state.source = initial_src
    app.state.classifier = clsf
    app.state.hub = hub
    app.state.source_name = "presage" if isinstance(initial_src, PresageVitalsSource) else "mock"
    app.state.revert_task = None
    app.state.talkback_manager = tb_manager
    app.state.listen_hub = lh

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "source": app.state.source_name}

    @app.get("/api/source")
    async def get_source():
        """Returns the currently active telemetry mode (SIMULATED vs REALTIME)."""
        is_mock = isinstance(hub.source, MockVitalsSource)
        return {
            "source": "mock" if is_mock else "real",
            "mode": "SIMULATED" if is_mock else "REALTIME",
            "gate": getattr(getattr(presage_src, "gate", None), "reason", "disabled"),
        }

    @app.post("/api/source")
    async def set_source(req: SetSourceRequest):
        """Switches dynamically between simulated mock data and real camera/Presage sensor."""
        target = req.source.lower().strip()
        if target in ("mock", "simulated", "sim"):
            hub.set_source(mock_src)
            app.state.source = mock_src
            app.state.source_name = "mock"
            logger.info("Switched telemetry source to SIMULATED (Mock)")
        elif target in ("real", "presage", "camera", "realtime", "sensor"):
            hub.set_source(presage_src)
            app.state.source = presage_src
            app.state.source_name = "presage"
            logger.info("Switched telemetry source to REALTIME (Presage / Camera Sensor)")
        else:
            return JSONResponse({"error": "Invalid source. Use 'mock' or 'real'"}, status_code=400)

        sync_presage_pause()
        await hub.step()
        return await get_source()

    @app.get("/api/state")
    async def get_state():
        return hub.get_latest_payload()

    @app.get("/api/camera")
    async def get_camera():
        return {"enabled": cam.is_enabled(), "live": cam.is_live()}

    @app.post("/api/camera")
    async def set_camera(req: CameraToggleRequest):
        """Turn the camera on or off. Off releases the device and ends the Presage session
        (no Presage credits are used while it is off)."""
        cam.set_enabled(req.enabled)
        sync_presage_pause()
        logger.info("Camera %s via API", "enabled" if req.enabled else "disabled")
        await hub.step()  # push the new state to viewers immediately
        return {"enabled": cam.is_enabled(), "live": cam.is_live()}

    @app.post("/api/simulate-restless")
    async def simulate_restless(req: SimulateRestlessRequest | None = None):
        seconds = req.seconds if req is not None else 15.0
        expiry_epoch = clsf.force_restless(duration_s=seconds)
        if hasattr(hub.source, "set_forced_mode"):
            hub.source.set_forced_mode("RESTLESS")

        if getattr(app.state, "revert_task", None):
            app.state.revert_task.cancel()

        # Schedule resetting source mode after duration
        async def _revert():
            try:
                await asyncio.sleep(seconds)
                if hasattr(hub.source, "set_forced_mode"):
                    hub.source.set_forced_mode(None)
            except asyncio.CancelledError:
                pass

        app.state.revert_task = asyncio.create_task(_revert())
        await hub.step()

        expiry_dt = datetime.fromtimestamp(expiry_epoch, tz=UTC)
        iso_str = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return JSONResponse({"forced_until": iso_str})

    @app.post("/api/simulate-unstable")
    async def simulate_unstable(req: SimulateRestlessRequest | None = None):
        seconds = req.seconds if req is not None else 15.0
        expiry_epoch = hub.force_unstable(seconds)
        await hub.step()
        expiry_dt = datetime.fromtimestamp(expiry_epoch, tz=UTC)
        iso_str = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return JSONResponse({"forced_until": iso_str})

    @app.post("/api/soothe/play")
    async def play_edge_soothe(req: PlaySootheRequest | None = None):
        """Plays soothing parent voice or calming chime directly on Pi hardware speaker."""
        audio_data = req.audio_base64 if req else None
        success = edge_player.play_base64_or_default(audio_data)
        return {"status": "playing" if success else "failed", "phrase": req.phrase if req else None}

    @app.post("/api/soothe/stop")
    async def stop_edge_soothe():
        """Silences the Pi hardware speaker."""
        edge_player.stop()
        return {"status": "stopped"}

    @app.get("/api/soothe/status")
    async def edge_soothe_status():
        """Returns playback status of the Pi hardware speaker."""
        return {"is_playing": edge_player.is_playing}

    @app.get("/video_feed")
    async def video_feed(request: Request, limit: int | None = None):
        async def mjpeg_generator() -> AsyncGenerator[bytes, None]:
            try:
                async for part in _stream_new_frames(request, cam, cam.get_latest_frame_jpeg, limit):
                    yield part
            except (asyncio.CancelledError, GeneratorExit):
                return

        return StreamingResponse(
            mjpeg_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/video_feed/debug")
    async def video_feed_debug(request: Request, limit: int | None = None):
        async def mjpeg_generator() -> AsyncGenerator[bytes, None]:
            cam.acquire_debug()
            try:
                async for part in _stream_new_frames(request, cam, cam.get_latest_debug_jpeg, limit):
                    yield part
            except (asyncio.CancelledError, GeneratorExit):
                return
            finally:
                cam.release_debug()

        return StreamingResponse(
            mjpeg_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(websocket: WebSocket):
        await hub.connect(websocket)
        try:
            while True:
                # Keep socket alive and listen for client messages / ping-pong
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(websocket)

    # Talkback: parent -> Pi speaker
    @app.websocket("/ws/talk")
    async def ws_talk(websocket: WebSocket):
        await handle_talkback_ws(tb_manager, websocket)

    # Listen: Pi mic -> browser
    @app.websocket("/ws/listen")
    async def ws_listen(websocket: WebSocket):
        await handle_listen_ws(lh, websocket)

    # Night vision control
    @app.get("/api/night-vision")
    async def get_night_vision():
        cam_obj: Camera = app.state.camera
        return {
            "mode": cam_obj.get_night_vision_mode(),
            "active": cam_obj.is_enhancing(),
        }

    @app.post("/api/night-vision")
    async def set_night_vision(req: NightVisionModeRequest):
        cam_obj: Camera = app.state.camera
        cam_obj.set_night_vision_mode(req.mode)
        return {
            "mode": cam_obj.get_night_vision_mode(),
            "active": cam_obj.is_enhancing(),
        }

    # Audio capabilities
    @app.get("/api/audio/capabilities")
    async def audio_capabilities():
        import shutil
        talk = shutil.which("aplay") is not None or shutil.which("ffplay") is not None
        listen = settings.listen_enabled and shutil.which("arecord") is not None
        return {"talk": talk, "listen": listen}

    return app


app = create_app()
