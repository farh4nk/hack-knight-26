"""Camera capture thread with frame-diff motion estimation and fallback frame."""

import logging
import threading
import time

import cv2
import numpy as np

from cradleecho.config import settings

logger = logging.getLogger(__name__)


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
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Pre-generate synthetic fallback frame
        fallback_mat = create_synthetic_frame("NO CAMERA")
        success, encoded = cv2.imencode(".jpg", fallback_mat, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        self._fallback_jpeg: bytes = encoded.tobytes() if success else b""
        self._latest_jpeg: bytes = self._fallback_jpeg

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

    def _capture_loop(self) -> None:
        cap: cv2.VideoCapture | None = None
        prev_gray: np.ndarray | None = None

        # If dummy or none specified, keep serving fallback frame without trying hardware
        use_hardware = self._device not in ("none", "dummy", "synthetic", -1)

        try:
            if use_hardware:
                logger.info("Opening camera device: %s", self._device)
                cap = cv2.VideoCapture(self._device)
                if cap is not None and cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                else:
                    logger.warning("Could not open camera device %s; using synthetic feed", self._device)
            else:
                logger.info("Using synthetic fallback feed for camera")

            while not self._stop_event.is_set():
                frame = None
                if cap is not None and cap.isOpened():
                    ret, raw_frame = cap.read()
                    if ret and raw_frame is not None:
                        frame = raw_frame

                if frame is not None:
                    # Compute frame-diff motion
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    mean_val = float(np.mean(gray))
                    with self._lock:
                        if self._mean_brightness is None:
                            self._mean_brightness = mean_val
                        else:
                            self._mean_brightness = 0.1 * mean_val + 0.9 * self._mean_brightness
                        self._is_live = True

                    blurred = cv2.GaussianBlur(gray, (21, 21), 0)

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

                    ret_enc, enc_jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    if ret_enc:
                        with self._lock:
                            self._latest_jpeg = enc_jpeg.tobytes()

                    time.sleep(0.033)  # ~30 fps
                else:
                    # Fallback synthetic frame
                    with self._lock:
                        self._latest_jpeg = self._fallback_jpeg
                        self._motion_index = 0.0
                        self._is_live = False
                    time.sleep(0.05)  # 20 fps for synthetic fallback

        except Exception as e:
            logger.error("Exception in camera capture loop: %s", e)
            with self._lock:
                self._latest_jpeg = self._fallback_jpeg
                self._motion_index = 0.0
        finally:
            if cap is not None:
                cap.release()
            logger.info("Camera capture loop stopped")
