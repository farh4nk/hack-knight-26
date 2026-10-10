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

from cradleecho.config import settings

logger = logging.getLogger(__name__)

NIGHT_VISION_MODES = {"OFF", "AUTO", "ON"}


def enhance_low_light(frame: np.ndarray, brightness: float) -> np.ndarray:
    """Enhance a low-light BGR frame using gain + CLAHE on L channel.

    Args:
        frame: Input BGR frame (uint8).
        brightness: Current mean brightness (0-255), used to scale gain.

    Returns:
        Enhanced BGR frame (uint8).
    """
    # Convert to LAB
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # Global gain: only boost when brightness < 100; no change at 100+
    norm_brightness = min(1.0, max(0.0, brightness / 100.0))
    gain = max(1.0, 3.0 - 2.0 * norm_brightness)  # 3.0 at 0, 1.0 at 100, 1.0 above
    l_gained = cv2.convertScaleAbs(l, alpha=gain, beta=0)

    # CLAHE on gained L channel
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_gained)

    # Merge and convert back
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


def create_synthetic_frame(text: str = "NO CAMERA") -> np.ndarray:
    """Create a 640x480 synthetic BGR fallback image."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Slate gray background with subtle vignette
    img[:] = (38, 32, 28)

    # Frame border
    cv2.rectangle(img, (20, 20), (620, 460), (70, 60, 55), 2)

    # Title & status text
    cv2.putText(
        img,
        "CRADLEECHO MONITOR",
        (160, 200),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (220, 220, 220),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        text,
        (220, 250),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (80, 140, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "SIGNAL UNSTABLE / CHECK CONNECTION",
        (130, 300),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (160, 160, 160),
        1,
        cv2.LINE_AA,
    )
    return img


class Camera:
    """Single shared background camera capture thread."""

    def __init__(self, device: int | str | None = None) -> None:
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

        # Night vision
        self._night_vision_mode: str = settings.night_vision_mode.upper()
        if self._night_vision_mode not in NIGHT_VISION_MODES:
            self._night_vision_mode = "AUTO"
        self._night_on_below: float = settings.night_on_below
        self._night_off_above: float = settings.night_off_above
        self._enhancing: bool = False
        self._brightness_ema: float | None = None  # separate EMA for night vision hysteresis

        # Pre-generate synthetic fallback frame
        fallback_mat = create_synthetic_frame("NO CAMERA")
        success, encoded = cv2.imencode(".jpg", fallback_mat, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        self._fallback_jpeg: bytes = encoded.tobytes() if success else b""
        self._latest_jpeg: bytes = self._fallback_jpeg
        self._debug_viewers: int = 0
        self._latest_debug_jpeg: bytes = b""
        self._frame_seq: int = 0  # bumped whenever a new JPEG is published

        # Newest raw frame from the reader thread; older frames are dropped, never queued.
        self._raw_cond = threading.Condition()
        self._latest_raw: np.ndarray | None = None
        self._raw_seq: int = 0

    def get_night_vision_mode(self) -> str:
        """Return current night vision mode (OFF, AUTO, ON)."""
        with self._lock:
            return self._night_vision_mode

    def set_night_vision_mode(self, mode: str) -> None:
        """Set night vision mode. Must be OFF, AUTO, or ON."""
        mode = mode.upper()
        if mode not in NIGHT_VISION_MODES:
            raise ValueError(f"Invalid night vision mode: {mode}")
        with self._lock:
            self._night_vision_mode = mode
            if mode == "OFF":
                self._enhancing = False
            elif mode == "ON":
                self._enhancing = True

    def is_enhancing(self) -> bool:
        """Return whether night vision enhancement is currently active."""
        with self._lock:
            return self._enhancing

    def _update_enhancing_state(self) -> None:
        """Update enhancing state based on current mode and brightness EMA.
        
        This is exposed for testing; in production it's called from the capture loop.
        """
        with self._lock:
            mode = self._night_vision_mode
            if mode == "ON":
                self._enhancing = True
            elif mode == "AUTO":
                b = self._brightness_ema
                if b is not None:
                    if not self._enhancing and b < self._night_on_below:
                        self._enhancing = True
                    elif self._enhancing and b > self._night_off_above:
                        self._enhancing = False
            else:  # OFF
                self._enhancing = False

    def set_overlay(self, fn: Callable[[np.ndarray], None] | None) -> None:
        """Set a callback to draw an overlay on the encoded MJPEG frame."""
        with self._lock:
            self._overlay_fn = fn


    def start(self) -> None:
        """Start the background capture thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, name="CameraCaptureThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop capture thread and release resources."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def add_frame_listener(self, listener: Callable[[np.ndarray], None]) -> None:
        """Register a callback receiving each live BGR frame on the capture thread.

        Listeners must return quickly and never block.
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

    def _reader_loop(self, cap: "cv2.VideoCapture") -> None:
        """Drain the camera as fast as it delivers, keeping only the newest frame.

        Decoupling the read from the processing below is what keeps latency flat: if processing
        is briefly slower than the camera, frames are dropped instead of queueing up inside
        OpenCV/ffmpeg (which showed up as multi-second delay).
        """
        while not self._stop_event.is_set():
            ret, frame = cap.read()
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

    def _capture_loop(self) -> None:
        cap: cv2.VideoCapture | None = None
        reader: threading.Thread | None = None
        prev_gray: np.ndarray | None = None
        seen_seq = 0

        # If dummy or none specified, keep serving fallback frame without trying hardware
        use_hardware = self._device not in ("none", "dummy", "synthetic", -1)

        try:
            if use_hardware:
                logger.info("Opening camera device: %s", self._device)
                cap = cv2.VideoCapture(self._device)
                if cap is not None and cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # best effort; honoured by V4L2
                    reader = threading.Thread(
                        target=self._reader_loop, args=(cap,), name="CameraReaderThread", daemon=True
                    )
                    reader.start()
                else:
                    logger.warning("Could not open camera device %s; using synthetic feed", self._device)
            else:
                logger.info("Using synthetic fallback feed for camera")

            while not self._stop_event.is_set():
                frame = None
                if reader is not None:
                    seen_seq, frame = self._next_frame(seen_seq)

                if frame is not None:
                    # Frame listeners (Presage, etc.) ALWAYS get the raw frame
                    for listener in self._frame_listeners:
                        try:
                            listener(frame)
                        except Exception:
                            logger.exception("Frame listener failed")

                    # Frame-diff motion on a half-size image: ~4x cheaper than full-size, and an
                    # 11px blur at half-size matches the old 21px blur at full-size.
                    # Use RAW frame for motion/brightness computation
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    small = cv2.resize(gray, (320, 240), interpolation=cv2.INTER_AREA)

                    mean_val = float(np.mean(small))
                    with self._lock:
                        if self._mean_brightness is None:
                            self._mean_brightness = mean_val
                        else:
                            self._mean_brightness = 0.1 * mean_val + 0.9 * self._mean_brightness
                        # Separate EMA for night vision hysteresis (slightly faster response)
                        if self._brightness_ema is None:
                            self._brightness_ema = mean_val
                        else:
                            self._brightness_ema = 0.2 * mean_val + 0.8 * self._brightness_ema
                        self._is_live = True

                        # Update night vision enhancing state based on mode
                        mode = self._night_vision_mode
                        if mode == "ON":
                            self._enhancing = True
                        elif mode == "AUTO":
                            b = self._brightness_ema
                            if b is not None:
                                if not self._enhancing and b < self._night_on_below:
                                    self._enhancing = True
                                elif self._enhancing and b > self._night_off_above:
                                    self._enhancing = False
                        else:  # OFF
                            self._enhancing = False

                        enhancing = self._enhancing
                        brightness_for_enhance = self._brightness_ema

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

                    # Prepare frame for encoding: apply night vision enhancement if active
                    encode_frame = frame
                    if enhancing and brightness_for_enhance is not None:
                        encode_frame = enhance_low_light(frame, brightness_for_enhance)

                    # Always encode the (potentially enhanced) frame
                    ret_enc, enc_jpeg = cv2.imencode(".jpg", encode_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])

                    # Conditionally encode debug frame
                    debug_bytes = b""
                    if overlay_fn is not None and debug_count > 0:
                        view = encode_frame.copy()
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
            if reader is not None:
                reader.join(timeout=2.0)
            # Releasing while the reader is stuck in cap.read() (stalled network source) is unsafe.
            if cap is not None and (reader is None or not reader.is_alive()):
                cap.release()
            logger.info("Camera capture loop stopped")
