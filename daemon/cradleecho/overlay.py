import cv2
import numpy as np

def draw_vitals_panel(
    frame_bgr: np.ndarray,
    payload: dict | None,
    sdk_hint: str = "",
    session_running: bool | None = None
) -> None:
    if frame_bgr is None:
        return

    h, w = frame_bgr.shape[:2]

    lines = []
    
    if session_running is not None:
        if session_running:
            lines.append([("PRESAGE: running", (200, 200, 200))])
        else:
            lines.append([("PRESAGE: idle (gate closed)", (100, 100, 100))])

    if payload is None:
        payload = {}

    vitals = payload.get("vitals", {})
    if vitals is None:
        vitals = {}
        
    brpm = vitals.get("brpm")
    bpm = vitals.get("bpm")
    conf = vitals.get("confidence")
    state = payload.get("state", "--")

    brpm_str = f"{brpm:.1f}" if isinstance(brpm, (int, float)) else "--"
    bpm_str = f"{bpm:.0f}" if isinstance(bpm, (int, float)) else "--"
    conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "--"

    conf_val = float(conf) if isinstance(conf, (int, float)) else 0.0
    conf_color = (0, 255, 0) if conf_val >= 0.40 else (0, 165, 255)

    v1 = f"BrPM {brpm_str}   BPM {bpm_str}   "
    v2 = f"conf {conf_str}"
    lines.append([(v1, (255, 255, 255)), (v2, conf_color)])

    lines.append([(f"STATE: {state}", (255, 255, 255))])

    if sdk_hint:
        hint_str = f"SDK: {sdk_hint}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        
        truncated = hint_str
        (tw, th), _ = cv2.getTextSize(truncated, font, font_scale, thickness)
        margin = 10
        while tw > w - 2 * margin and len(truncated) > 4:
            truncated = truncated[:-1]
            (tw, th), _ = cv2.getTextSize(truncated + "...", font, font_scale, thickness)
        if truncated != hint_str:
            truncated += "..."
        lines.append([(truncated, (150, 150, 255))])

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    margin = 10
    line_height = 20

    max_text_w = 0
    for segments in lines:
        line_w = 0
        for text, color in segments:
            (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
            line_w += tw
        max_text_w = max(max_text_w, line_w)

    panel_w = max_text_w + 2 * margin
    panel_h = len(lines) * line_height + 2 * margin

    x1 = 0
    y1 = h - panel_h
    x2 = panel_w
    y2 = h

    if y1 < 0: y1 = 0
    if x2 > w: x2 = w

    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame_bgr, 0.4, 0, frame_bgr)

    y_offset = y1 + margin + 12
    for segments in lines:
        x_offset = margin
        for text, color in segments:
            cv2.putText(frame_bgr, text, (x_offset, y_offset), font, font_scale, color, thickness, cv2.LINE_AA)
            (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
            x_offset += tw
        y_offset += line_height
