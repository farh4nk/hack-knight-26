"""Camera capture thread with frame-diff motion estimation and fallback frame."""

import logging
import os
import threading
import time
from collections.abc import Callable

# Network (HTTP/RTSP) sources go through OpenCV's ffmpeg backend, which buffers aggressively by
# default and adds seconds of delay. Must be set before cv2 opens a capture; ignored by V4L2.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "fflags;nobuffer|flags;low_delay|probesize;65536|analyzeduration;0",
)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from cradleecho import diag
from cradleecho.config import settings

logger = logging.getLogger(__name__)


def create_synthetic_frame(
    text: str = "NO CAMERA", subtitle: str = "SIGNAL UNSTABLE / CHECK CONNECTION"
) -> np.ndarray:
    """Create a 640x480 synthetic BGR placeholder image."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Slate gray background with subtle vignette
    img[:] = (38, 32, 28)

    # Frame border
    cv2.rectangle(img, (20, 20), (620, 460), (70, 60, 55), 2)

    def centered(msg: str, y: int, scale: float, color: tuple[int, int, int], thickness: int) -> None:
        (w, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        cv2.putText(img, msg, ((640 - w) // 2, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

    centered("CRADLEECHO MONITOR", 200, 0.9, (220, 220, 220), 2)
    centered(text, 250, 0.8, (80, 140, 255), 2)
    centered(subtitle, 300, 0.55, (160, 160, 160), 1)
    return img


class Camera:
    """Single shared background camera capture thread."""

    def __init__(self, device: int | str | None = None, enabled: bool | None = None) -> None:
        if device is None:
            raw_dev = settings.camera
            if raw_dev.isdigit():
                self._device: int | str = int(raw_dev)
            else:
                self._device = raw_dev
        else:
            self._device = device

        self._motion_index: float = 0.0
        self._mean_brightness: float | None = None
        self._is_live: bool = False
        self._lock = threading.Lock()
        self._frame_listeners: list[Callable[[np.ndarray], None]] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._overlay_fn: Callable[[np.ndarray], None] | None = None

        # User-controlled on/off. Off releases the device and serves a placeholder; the capture
        # loop waits on this event while paused.
        self._enabled = threading.Event()
        if settings.camera_enabled if enabled is None else enabled:
            self._enabled.set()

        # Pre-generate synthetic fallback frame
        fallback_mat = create_synthetic_frame("NO CAMERA")
        success, encoded = cv2.imencode(".jpg", fallback_mat, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        self._fallback_jpeg: bytes = encoded.tobytes() if success else b""
        paused_mat = create_synthetic_frame("CAMERA OFF", "Turn the camera on to resume monitoring")
        success, encoded = cv2.imencode(".jpg", paused_mat, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        self._paused_jpeg: bytes = encoded.tobytes() if success else b""
        self._latest_jpeg: bytes = self._paused_jpeg if not self._enabled.is_set() else self._fallback_jpeg
        self._debug_viewers: int = 0
        self._latest_debug_jpeg: bytes = b""
        self._frame_seq: int = 0  # bumped whenever a new JPEG is published

        # Newest raw frame from the reader thread; older frames are dropped, never queued.
        self._raw_cond = threading.Condition()
        self._latest_raw: np.ndarray | None = None
        self._raw_seq: int = 0

        # Listeners (face gate, Presage push) run on their own thread, newest frame only, so
        # their cost never slows capture, motion or the MJPEG stream.
        self._listener_cond = threading.Condition()
        self._listener_frame: np.ndarray | None = None
        self._listener_seq: int = 0
        self._listener_thread: threading.Thread | None = None

    def set_overlay(self, fn: Callable[[np.ndarray], None] | None) -> None:
        """Set a callback to draw an overlay on the encoded MJPEG frame."""
        with self._lock:
            self._overlay_fn = fn


    def set_enabled(self, enabled: bool) -> None:
        """Turn the camera on or off. Off stops capture and releases the device."""
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()

    def is_enabled(self) -> bool:
        return self._enabled.is_set()

    def start(self) -> None:
        """Start the background capture thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, name="CameraCaptureThread", daemon=True)
        self._thread.start()
        self._listener_thread = threading.Thread(
            target=self._listener_loop, name="CameraListenerThread", daemon=True
        )
        self._listener_thread.start()

    def _listener_loop(self) -> None:
        seen = 0
        while not self._stop_event.is_set():
            with self._listener_cond:
                self._listener_cond.wait_for(
                    lambda: self._listener_seq != seen or self._stop_event.is_set(), timeout=0.5
                )
                if self._listener_seq == seen or self._listener_frame is None:
                    continue
                seen, frame = self._listener_seq, self._listener_frame
            t0 = time.perf_counter()
            for listener in list(self._frame_listeners):
                try:
                    listener(frame)
                except Exception:
                    logger.exception("Frame listener failed")
            diag.timed("listeners", time.perf_counter() - t0)

    def stop(self) -> None:
        """Stop capture thread and release resources."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._listener_cond:
            self._listener_cond.notify_all()
        if self._listener_thread is not None:
            self._listener_thread.join(timeout=2.0)
            self._listener_thread = None

    def add_frame_listener(self, listener: Callable[[np.ndarray], None]) -> None:
        """Register a callback receiving live BGR frames on the listener thread.

        Slow listeners skip frames (newest wins); they never slow capture.
        """
        self._frame_listeners.append(listener)

    def acquire_debug(self) -> None:
        with self._lock:
            self._debug_viewers += 1

    def release_debug(self) -> None:
        with self._lock:
            self._debug_viewers = max(0, self._debug_viewers - 1)

    def get_latest_debug_jpeg(self) -> bytes:
        with self._lock:
            return self._latest_debug_jpeg or self._latest_jpeg

    def get_frame_seq(self) -> int:
        """Counter that changes whenever a new JPEG is available (lets streams skip duplicates)."""
        with self._lock:
            return self._frame_seq

    def get_latest_frame_jpeg(self) -> bytes:
        """Return the most recent JPEG frame bytes."""
        with self._lock:
            return self._latest_jpeg

    def get_motion_index(self) -> float:
        """Return the current smoothed motion index (0.0 to 1.0)."""
        with self._lock:
            return self._motion_index

    def get_brightness(self) -> float | None:
        """Return the current smoothed brightness (0-255)."""
        with self._lock:
            return self._mean_brightness

    def is_live(self) -> bool:
        """Return whether real hardware frames are arriving."""
        with self._lock:
            return self._is_live

    def _reader_loop(self, cap: "cv2.VideoCapture", stop: threading.Event) -> None:
        """Drain the camera as fast as it delivers, keeping only the newest frame.

        Decoupling the read from the processing below is what keeps latency flat: if processing
        is briefly slower than the camera, frames are dropped instead of queueing up inside
        OpenCV/ffmpeg (which showed up as multi-second delay).
        """
        while not self._stop_event.is_set() and not stop.is_set():
            ret, frame = cap.read()
            if ret:
                diag.count("cam_delivered")
            if not ret and isinstance(self._device, str) and os.path.exists(self._device):
                # Rewind video file to frame 0 so recorded clips loop indefinitely
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            ok = bool(ret) and frame is not None
            with self._raw_cond:
                self._latest_raw = frame if ok else None
                self._raw_seq += 1
                self._raw_cond.notify_all()
            if not ok:
                time.sleep(0.05)

    def _next_frame(self, seen_seq: int, timeout: float = 0.5) -> tuple[int, np.ndarray | None]:
        """Block until the reader publishes a frame newer than `seen_seq`; None on stall."""
        with self._raw_cond:
            self._raw_cond.wait_for(
                lambda: self._raw_seq != seen_seq or self._stop_event.is_set(), timeout=timeout
            )
            if self._raw_seq == seen_seq:
                return seen_seq, None
            return self._raw_seq, self._latest_raw

    def _open_device(self):
        """Open the camera and start its reader thread: (cap, reader, reader_stop), or Nones."""
        logger.info("Opening camera device: %s", self._device)
        cap = cv2.VideoCapture(self._device)
        if cap is None or not cap.isOpened():
            logger.warning("Could not open camera device %s; using synthetic feed", self._device)
            return None, None, None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, settings.camera_fps)
        # Do NOT set CAP_PROP_BUFFERSIZE=1: with a single V4L2 buffer the driver cannot
        # capture while a frame is being read, which halves the rate (30 -> 15 fps on a
        # Pi 4 + UVC camera) and Presage then rejects the stream (< 25 fps). The reader
        # thread already drops stale frames, so extra buffers don't add latency.
        reader_stop = threading.Event()
        reader = threading.Thread(
            target=self._reader_loop, args=(cap, reader_stop), name="CameraReaderThread", daemon=True
        )
        reader.start()
        return cap, reader, reader_stop

    def _close_device(self, cap, reader, reader_stop) -> None:
        if reader_stop is not None:
            reader_stop.set()
        if reader is not None:
            reader.join(timeout=2.0)
        # Releasing while the reader is stuck in cap.read() (stalled network source) is unsafe.
        if cap is not None and (reader is None or not reader.is_alive()):
            cap.release()
        with self._raw_cond:
            self._latest_raw = None

    def _capture_loop(self) -> None:
        cap = reader = reader_stop = None
        prev_gray: np.ndarray | None = None
        seen_seq = 0
        open_failed = False
        paused_published = False

        # If dummy or none specified, keep serving fallback frame without trying hardware
        use_hardware = self._device not in ("none", "dummy", "synthetic", -1)

        try:
            if not use_hardware:
                logger.info("Using synthetic fallback feed for camera")

            while not self._stop_event.is_set():
                if not self._enabled.is_set():
                    # Turned off: release the device (the camera light goes out and Presage gets
                    # no frames) and serve a placeholder until it is turned back on.
                    if cap is not None or reader is not None:
                        self._close_device(cap, reader, reader_stop)
                        cap = reader = reader_stop = None
                        prev_gray = None
                        logger.info("Camera turned off")
                    open_failed = False
                    if not paused_published:
                        paused_published = True
                        with self._lock:
                            self._latest_jpeg = self._paused_jpeg
                            self._latest_debug_jpeg = b""
                            self._motion_index = 0.0
                            self._mean_brightness = None
                            self._is_live = False
                            self._frame_seq += 1
                    self._enabled.wait(timeout=0.25)
                    continue
                if paused_published:
                    paused_published = False
                    logger.info("Camera turned on")
                if use_hardware and cap is None and not open_failed:
                    cap, reader, reader_stop = self._open_device()
                    open_failed = cap is None
                    with self._raw_cond:
                        seen_seq = self._raw_seq

                frame = None
                if reader is not None:
                    seen_seq, frame = self._next_frame(seen_seq)

                if frame is not None:
                    diag.count("loop_frames")
                    with self._listener_cond:
                        self._listener_frame = frame
                        self._listener_seq += 1
                        self._listener_cond.notify_all()

                    # Frame-diff motion on a half-size image: ~4x cheaper than full-size, and an
                    # 11px blur at half-size matches the old 21px blur at full-size.
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    small = cv2.resize(gray, (320, 240), interpolation=cv2.INTER_AREA)

                    mean_val = float(np.mean(small))
                    with self._lock:
                        if self._mean_brightness is None:
                            self._mean_brightness = mean_val
                        else:
                            self._mean_brightness = 0.1 * mean_val + 0.9 * self._mean_brightness
                        self._is_live = True

                    blurred = cv2.GaussianBlur(small, (11, 11), 0)

                    if prev_gray is not None:
                        diff = cv2.absdiff(prev_gray, blurred)
                        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                        motion_ratio = float(np.count_nonzero(thresh)) / float(thresh.size)
                        # Normalize to 0-1 and clamp
                        motion_val = min(1.0, motion_ratio * 6.0)
                        # Exponential moving average (EMA)
                        with self._lock:
                            self._motion_index = 0.3 * motion_val + 0.7 * self._motion_index
                    prev_gray = blurred

                    with self._lock:
                        overlay_fn = self._overlay_fn
                        debug_count = self._debug_viewers

                    # Always encode the clean frame
                    ret_enc, enc_jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])

                    # Conditionally encode debug frame
                    debug_bytes = b""
                    if overlay_fn is not None and debug_count > 0:
                        view = frame.copy()
                        try:
                            overlay_fn(view)
                        except Exception:
                            logger.exception("Overlay failed")

                        ret_debug, enc_debug = cv2.imencode(".jpg", view, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                        if ret_debug:
                            debug_bytes = enc_debug.tobytes()

                    with self._lock:
                        if ret_enc:
                            self._latest_jpeg = enc_jpeg.tobytes()
                        self._latest_debug_jpeg = debug_bytes
                        self._frame_seq += 1
                    # No fixed sleep: _next_frame() blocks until the camera has a new frame.
                else:
                    # Fallback synthetic frame
                    with self._lock:
                        self._latest_jpeg = self._fallback_jpeg
                        self._latest_debug_jpeg = b""
                        self._motion_index = 0.0
                        self._is_live = False
                    if reader is None:
                        time.sleep(0.05)  # 20 fps for synthetic fallback

        except Exception as e:
            logger.error("Exception in camera capture loop: %s", e)
            with self._lock:
                self._latest_jpeg = self._fallback_jpeg
                self._latest_debug_jpeg = b""
                self._motion_index = 0.0
        finally:
            self._stop_event.set()  # release the reader thread if we exited on an error
            self._close_device(cap, reader, reader_stop)
            logger.info("Camera capture loop stopped")
