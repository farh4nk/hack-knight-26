"""Guards against the frame-backlog bug: a slow consumer must see the newest frame, not an old one."""

import queue
import threading
import time

import numpy as np

from cradleecho.camera import Camera


class BufferedCap:
    """Fake camera with an internal FIFO like ffmpeg/V4L2: 100 fps in, read() pops the oldest."""

    def __init__(self) -> None:
        self.produced = 0
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stop = threading.Event()
        threading.Thread(target=self._produce, daemon=True).start()

    def _produce(self) -> None:
        while not self._stop.is_set():
            self.produced += 1
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[0, 0] = (self.produced & 255, (self.produced >> 8) & 255, 0)
            self._q.put(frame)
            time.sleep(0.01)

    def isOpened(self) -> bool:
        return True

    def read(self):
        try:
            return True, self._q.get(timeout=1.0)
        except queue.Empty:
            return False, None

    def set(self, prop, val) -> None:
        pass

    def release(self) -> None:
        self._stop.set()


def test_slow_consumer_sees_newest_frame(monkeypatch):
    cap = BufferedCap()
    monkeypatch.setattr("cv2.VideoCapture", lambda x: cap)

    last_seen = {"n": 0}

    def slow_listener(frame: np.ndarray) -> None:
        last_seen["n"] = int(frame[0, 0, 0]) + 256 * int(frame[0, 0, 1])
        time.sleep(0.05)  # ~20 fps consumer against a 100 fps source

    cam = Camera(device="0")
    cam.add_frame_listener(slow_listener)
    cam.start()
    try:
        time.sleep(1.5)
        lag_frames = cap.produced - last_seen["n"]
        # Without the reader thread this lags by ~100+ frames (1s+) and keeps growing.
        assert lag_frames <= 15, f"consumer is {lag_frames} frames behind the camera"
    finally:
        cam.stop()
        cap.release()


def test_capture_requests_fps_and_never_caps_buffer(monkeypatch):
    """CAP_PROP_BUFFERSIZE=1 halved a Pi 4 + UVC camera to 15 fps, below Presage's 25 fps minimum."""
    import cv2

    set_calls: list[int] = []

    class RecordingCap(BufferedCap):
        def set(self, prop, val) -> None:
            set_calls.append(prop)

    cap = RecordingCap()
    monkeypatch.setattr("cv2.VideoCapture", lambda x: cap)
    cam = Camera(device="0")
    cam.start()
    try:
        time.sleep(0.3)
    finally:
        cam.stop()
        cap.release()

    assert cv2.CAP_PROP_BUFFERSIZE not in set_calls
    assert cv2.CAP_PROP_FPS in set_calls


def test_night_vision_enhances_preview_but_not_listener_frames(monkeypatch):
    """Presage and the face gate must see the raw frame; only the MJPEG preview is enhanced."""
    import cv2

    class DarkCap(BufferedCap):
        def read(self):
            ok, frame = super().read()
            if ok:
                frame[:] = 20  # dark, uniform scene so enhancement visibly brightens it
            return ok, frame

    cap = DarkCap()
    monkeypatch.setattr("cv2.VideoCapture", lambda x: cap)

    seen: list[float] = []
    cam = Camera(device="0")
    cam.set_night_vision_mode("ON")
    cam.add_frame_listener(lambda f: seen.append(float(f.mean())))
    cam.start()
    try:
        time.sleep(1.5)
        jpeg = cam.get_latest_frame_jpeg()
    finally:
        cam.stop()
        cap.release()

    assert seen, "listener received no frames"
    assert max(seen) < 25, "listener frame was enhanced"
    preview = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert preview.mean() > 30, "preview was not enhanced"
