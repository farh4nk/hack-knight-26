#!/usr/bin/env python3
"""Serve a host webcam as an MJPEG stream so a container can read it over HTTP.

Docker on macOS/Windows can't pass a camera device into a container, so run this
on the host and point the daemon at it:

    CRADLEECHO_CAMERA=http://host.docker.internal:8090/video

Works on any OS OpenCV supports. Usage:
    python scripts/camera_publisher.py [--device 0] [--port 8090]
"""

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class FrameGrabber(threading.Thread):
    """Reads the camera continuously and keeps the newest JPEG for all clients."""

    def __init__(self, device: int, width: int, height: int) -> None:
        super().__init__(daemon=True)
        self.cap = cv2.VideoCapture(device)
        if not self.cap.isOpened():
            raise SystemExit(
                f"Could not open camera {device}. On macOS, allow camera access for your "
                "terminal in System Settings > Privacy & Security > Camera."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.jpeg: bytes | None = None
        self.lock = threading.Lock()

    def run(self) -> None:
        while True:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                with self.lock:
                    self.jpeg = buf.tobytes()

    def latest(self) -> bytes | None:
        with self.lock:
            return self.jpeg


def make_handler(grabber: FrameGrabber, fps: float):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/healthz":
                self.send_response(200 if grabber.latest() else 503)
                self.end_headers()
                return
            if self.path != "/video":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    jpeg = grabber.latest()
                    if jpeg:
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(jpeg)).encode()
                            + b"\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                    time.sleep(1 / fps)
            except (BrokenPipeError, ConnectionResetError):
                pass  # client disconnected

        def log_message(self, *args) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()

    grabber = FrameGrabber(args.device, args.width, args.height)
    grabber.start()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(grabber, args.fps))
    print(f"Publishing camera {args.device} at http://0.0.0.0:{args.port}/video", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
