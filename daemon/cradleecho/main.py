"""CradleEcho Edge Daemon FastAPI application."""

import asyncio
import logging
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
from cradleecho.sources.presage import PresageVitalsSource
from cradleecho.telemetry import TelemetryHub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cradleecho")


class SimulateRestlessRequest(BaseModel):
    seconds: float = Field(default=15.0, ge=1.0, le=300.0)


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


def create_app(
    camera: Camera | None = None,
    source: VitalsSource | None = None,
    classifier: SleepStateClassifier | None = None,
) -> FastAPI:
    cam = camera or Camera()
    src = source or build_source()
    clsf = classifier or SleepStateClassifier()
    gate = None
    if isinstance(src, PresageVitalsSource) and src.wants_frames:
        if settings.face_gate:
            from cradleecho.facegate import FaceGate
            gate = FaceGate(
                chest_room=settings.gate_chest_room,
                min_face_frac=settings.gate_min_face_frac,
            )
            src.set_gate(gate)
        cam.add_frame_listener(src.push_frame)
    hub = TelemetryHub(cam, src, clsf, interval_s=0.5)

    if settings.debug_overlay:
        from cradleecho.overlay import draw_vitals_panel
        def _composite_overlay(frame):
            if gate is not None:
                gate.draw_overlay(frame)
            hint = getattr(src, 'validation_hint', '')
            session_running = src.session_running if isinstance(src, PresageVitalsSource) else None
            draw_vitals_panel(
                frame,
                hub.get_latest_payload(),
                sdk_hint=hint,
                session_running=session_running,
            )
        cam.set_overlay(_composite_overlay)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting CradleEcho daemon services...")
        cam.start()
        await src.start()
        await hub.start()
        yield
        logger.info("Shutting down CradleEcho daemon services...")
        await hub.stop()
        await src.stop()
        cam.stop()

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
    app.state.source = src
    app.state.classifier = clsf
    app.state.hub = hub
    app.state.source_name = "presage" if isinstance(src, PresageVitalsSource) else "mock"
    app.state.revert_task = None

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "source": app.state.source_name}

    @app.get("/api/state")
    async def get_state():
        return hub.get_latest_payload()

    @app.post("/api/simulate-restless")
    async def simulate_restless(req: SimulateRestlessRequest | None = None):
        seconds = req.seconds if req is not None else 15.0
        expiry_epoch = clsf.force_restless(duration_s=seconds)
        src.set_forced_mode("RESTLESS")

        if getattr(app.state, "revert_task", None):
            app.state.revert_task.cancel()

        # Schedule resetting source mode after duration
        async def _revert():
            try:
                await asyncio.sleep(seconds)
                src.set_forced_mode(None)
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

    @app.get("/video_feed")
    async def video_feed(request: Request, limit: int | None = None):
        async def mjpeg_generator() -> AsyncGenerator[bytes, None]:
            count = 0
            try:
                # `limit` is test-only; is_disconnected() can block under TestClient
                while limit is not None or not await request.is_disconnected():
                    frame_bytes = cam.get_latest_frame_jpeg()
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + frame_bytes
                        + b"\r\n"
                    )
                    count += 1
                    if limit is not None and count >= limit:
                        break
                    await asyncio.sleep(0.04)  # ~25 fps
            except (asyncio.CancelledError, GeneratorExit):
                return

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

    return app


app = create_app()
