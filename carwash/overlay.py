"""Debug overlay drawn on the camera window - makes calibration and tuning visible."""

import cv2

from .guidance import MOVE_LEFT, MOVE_RIGHT, STOP, STRAIGHT, CONVEYOR_MOVING

COLORS = {  # BGR
    "tire_front_driver": (0, 255, 0),
    "tire_rear_driver": (255, 255, 0),
}
SIGNAL_COLORS = {
    MOVE_LEFT: (0, 200, 255), MOVE_RIGHT: (0, 200, 255), STRAIGHT: (0, 220, 0),
    STOP: (0, 0, 255), CONVEYOR_MOVING: (255, 160, 0),
}
SIGNAL_TEXT = {
    MOVE_LEFT: "TURN WHEEL LEFT", MOVE_RIGHT: "TURN WHEEL RIGHT", STRAIGHT: "STRAIGHT",
    STOP: "STOP", CONVEYOR_MOVING: "CONVEYOR MOVING",
}


def _text(img, s, org, color=(255, 255, 255), scale=0.55, thick=1):
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def draw_overlay(frame, detections, crop_box, contact_px, state, signal,
                 lateral, longitudinal, fps, uncalibrated, calib=None, search_area=None):
    img = frame.copy()
    if search_area is not None:
        cv2.polylines(img, [search_area], True, (0, 200, 255), 1)
    if crop_box is not None:
        x0, y0, x1, y1 = crop_box
        cv2.rectangle(img, (x0, y0), (x1, y1), (128, 128, 128), 1)
    for d in detections:
        c = COLORS.get(d.class_name, (255, 0, 255))
        cv2.rectangle(img, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), c, 2)
        _text(img, f"{d.class_name.replace('tire_', '')} {d.confidence:.2f}",
              (int(d.x1), max(12, int(d.y1) - 4)), c, 0.4)
    if contact_px is not None:
        cv2.circle(img, (int(contact_px[0]), int(contact_px[1])), 4, (0, 0, 255), -1)

    if calib is not None and not uncalibrated:
        _draw_centerline(img, calib)

    h = img.shape[0]
    _text(img, f"{state.name}", (10, 22))
    _text(img, SIGNAL_TEXT.get(signal, "WAIT"), (10, 50), SIGNAL_COLORS.get(signal, (200, 200, 200)), 0.8, 2)
    if lateral is not None:
        _text(img, f"lateral {lateral:+.1f} in   to stop {longitudinal:.1f} in", (10, 74))
    _text(img, f"{fps:.1f} fps", (10, h - 10), scale=0.45)
    if uncalibrated:
        _text(img, "UNCALIBRATED - positions meaningless", (10, h - 30), (0, 0, 255), 0.5)
    return img


def _draw_centerline(img, calib):
    """Project the x=0 line (and the stop line y=0) back into the image."""
    import numpy as np

    try:
        Hinv = np.linalg.inv(calib.H)
    except np.linalg.LinAlgError:
        return
    ys = calib.world_points[:, 1]
    xs = calib.world_points[:, 0]

    def to_px(wx, wy):
        p = Hinv @ np.array([wx, wy, 1.0])
        return int(p[0] / p[2]), int(p[1] / p[2])

    cv2.line(img, to_px(0, ys.min()), to_px(0, ys.max()), (255, 0, 255), 1)
    cv2.line(img, to_px(xs.min(), 0), to_px(xs.max(), 0), (0, 0, 255), 1)
