import time
import cv2

class FaceGate:
    def __init__(self, detector=None, min_face_frac=0.15, chest_room=1.75, center_tol=0.35, 
                 start_after_s=2.0, stop_after_s=10.0, detect_fps=5.0, clock=time.monotonic):
        self.min_face_frac = min_face_frac
        self.chest_room = chest_room
        self.center_tol = center_tol
        self.start_after_s = start_after_s
        self.stop_after_s = stop_after_s
        self.detect_interval = 1.0 / detect_fps if detect_fps > 0 else 0
        self.clock = clock

        if detector is None:
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                cascade = cv2.CascadeClassifier(cascade_path)
                if cascade.empty():
                    raise RuntimeError("Failed to load haarcascade_frontalface_default.xml")
                self.detector = lambda gray: cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))
            except AttributeError:
                raise RuntimeError("Failed to load haarcascade_frontalface_default.xml: cv2.CascadeClassifier not available")
        else:
            self.detector = detector

        self.reason = "no_face"
        self.is_active = False
        self._last_detect_time = -self.detect_interval
        self._last_ok_change_time = clock()
        self._last_ok_state = False
        self.last_boxes = []
        self.last_frame_size = (0, 0)
        self.last_room_ratio = None
        self.last_face_frac = 0.0

    def reset(self):
        self.reason = "no_face"
        self.is_active = False
        self._last_detect_time = -self.detect_interval
        self._last_ok_change_time = self.clock()
        self._last_ok_state = False
        self.last_boxes = []
        self.last_frame_size = (0, 0)
        self.last_room_ratio = None
        self.last_face_frac = 0.0

    def update(self, frame_bgr) -> bool:
        now = self.clock()
        if now - self._last_detect_time < self.detect_interval:
            return self.is_active

        self._last_detect_time = now

        h, w = frame_bgr.shape[:2]
        self.last_frame_size = (w, h)
        if w > 320:
            scale = 320 / w
            new_w, new_h = 320, int(h * scale)
            resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            scale = 1.0
            resized = frame_bgr
            new_w, new_h = w, h

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        faces = self.detector(gray)

        if isinstance(faces, tuple):
            faces = list(faces)

        self.last_boxes = []
        for f in faces:
            fx, fy, fw, fh = f
            self.last_boxes.append((int(fx / scale), int(fy / scale), int(fw / scale), int(fh / scale)))

        self.last_room_ratio = None
        self.last_face_frac = 0.0

        ok = False
        if len(faces) == 0:
            self.reason = "no_face"
        elif len(faces) > 1:
            self.reason = "multiple_faces"
        else:
            fx, fy, fw, fh = faces[0]
            center_x = fx + fw / 2.0
            frame_center = new_w / 2.0
            
            face_bottom = fy + fh
            self.last_room_ratio = (new_h - face_bottom) / fh if fh > 0 else 0
            self.last_face_frac = fh / new_h if new_h > 0 else 0

            if fh < self.min_face_frac * new_h:
                self.reason = "too_small"
            elif abs(center_x - frame_center) > self.center_tol * new_w:
                self.reason = "off_center"
            elif fy + fh + self.chest_room * fh > new_h:
                self.reason = "no_chest_room"
            else:
                self.reason = "ok"
                ok = True

        if ok != self._last_ok_state:
            self._last_ok_change_time = now
            self._last_ok_state = ok

        if ok and not self.is_active and (now - self._last_ok_change_time >= self.start_after_s):
            self.is_active = True
        elif not ok and self.is_active and (now - self._last_ok_change_time >= self.stop_after_s):
            self.is_active = False

        return self.is_active

    def progress(self) -> str:
        now = self.clock()
        if not self.is_active and self._last_ok_state:
            elapsed = now - self._last_ok_change_time
            return f"arming {elapsed:.1f}/{self.start_after_s:.1f}s"
        elif self.is_active and not self._last_ok_state:
            elapsed = now - self._last_ok_change_time
            return f"closing {elapsed:.1f}/{self.stop_after_s:.1f}s"
        return ""

    def draw_overlay(self, frame_bgr) -> None:
        h, w = frame_bgr.shape[:2]
        last_w, last_h = self.last_frame_size
        scale_x = w / last_w if last_w > 0 else 1.0
        scale_y = h / last_h if last_h > 0 else 1.0

        box_color = (0, 255, 0) if self.reason == 'ok' else (0, 165, 255)
        
        largest_box = None
        max_area = -1

        for (bx, by, bw, bh) in self.last_boxes:
            x = int(bx * scale_x)
            y = int(by * scale_y)
            bw_s = int(bw * scale_x)
            bh_s = int(bh * scale_y)
            cv2.rectangle(frame_bgr, (x, y), (x + bw_s, y + bh_s), box_color, 2)
            area = bw_s * bh_s
            if area > max_area:
                max_area = area
                largest_box = (x, y, bw_s, bh_s)

        if largest_box is not None:
            lx, ly, lw, lh = largest_box
            chest_h = int(self.chest_room * lh)
            cv2.rectangle(frame_bgr, (lx, ly + lh), (lx + lw, ly + lh + chest_h), (255, 255, 0), 1)

        lines = []
        if self.is_active:
            lines.append(("GATE OPEN", (0, 255, 0)))
        else:
            lines.append(("GATE CLOSED", (0, 0, 255)))
        
        lines.append((self.reason, (50, 50, 50)))
        prog = self.progress()
        if prog:
            lines.append((prog, (50, 50, 50)))

        if self.last_room_ratio is not None:
            room_str = f"{self.last_room_ratio:.2f}"
            face_str = f"{self.last_face_frac*100:.0f}%"
            passes = (self.last_room_ratio >= self.chest_room) and (self.last_face_frac >= self.min_face_frac)
            banner_color = (0, 255, 0) if passes else (0, 165, 255)
        else:
            room_str = "--"
            face_str = "--"
            banner_color = (0, 165, 255)

        banner = f"room {room_str} / need {self.chest_room:.2f}   face {face_str} / min {self.min_face_frac*100:.0f}%"
        lines.append((banner, banner_color))

        y_offset = 10
        for text, bg_color in lines:
            (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame_bgr, (10, y_offset), (10 + tw + 10, y_offset + th + 10), bg_color, cv2.FILLED)
            cv2.putText(frame_bgr, text, (15, y_offset + th + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += th + 15
