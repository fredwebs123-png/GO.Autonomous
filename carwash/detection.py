"""Tire detection: YOLO model plus an optional crop-then-detect step.

The bench mock-up uses a toy car whose tires are only 5-10 px wide in the
full camera frame, so the model was trained on 640x640 crops around the car
(roboflow/crop_car.py). RedCarCropper repeats that crop on live frames and
WheelDetector maps the boxes back to full-frame pixels, so everything after
detection (calibration, tracking, guidance) works in full-frame coordinates.

At full scale the tires should be large enough to run the model on the
whole frame: set "crop": null in the config and the cropper is skipped.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str  # e.g. "tire_front_driver"

    def ground_contact_pixel(self):
        """Bottom-center of the box - approximates where the tire meets the ground."""
        return (self.x1 + self.x2) / 2.0, self.y2


# ---------------------------------------------------------------------------
# Cropper (bench mock-up only)
# ---------------------------------------------------------------------------

class RedCarCropper:
    """Finds the red toy car and returns a padded square crop box.

    Same logic as roboflow/crop_car.py so live crops match the training crops.
    Mock-up only: a real vehicle can be any color.
    """

    def __init__(self, pad: float = 0.35, cell: int = 8, min_pixels: int = 40, search_area=None):
        """search_area: optional polygon [[x, y], ...] in frame pixels (e.g. the
        mat corners, set with set_search_area.py). Red outside it is ignored,
        so a red floor or wall can't be mistaken for the car."""
        self.pad = pad
        self.cell = cell
        self.min_pixels = min_pixels
        self.search_area = np.array(search_area, dtype=np.int32) if search_area else None
        self._area_mask = None  # built on first frame, once the size is known

    def find_crop(self, frame_bgr):
        """Return (x0, y0, x1, y1) in frame pixels, or None if no car is found."""
        mask = self._red_mask(frame_bgr)
        if self.search_area is not None:
            mask &= self._search_mask(mask.shape)
        box = self._largest_cluster_box(mask)
        if box is None:
            return None
        h, w = frame_bgr.shape[:2]
        return self._square_crop_box(box, w, h)

    def _search_mask(self, shape):
        if self._area_mask is None or self._area_mask.shape != shape:
            import cv2

            m = np.zeros(shape, dtype=np.uint8)
            cv2.fillPoly(m, [self.search_area], 1)
            self._area_mask = m.astype(bool)
        return self._area_mask

    @staticmethod
    def _red_mask(frame_bgr):
        arr = frame_bgr.astype(np.int16)
        b, g, r = arr[..., 0], arr[..., 1], arr[..., 2]
        return (r > 110) & (r - g > 60) & (r - b > 40)

    def _largest_cluster_box(self, mask):
        h, w = mask.shape
        cell = self.cell
        gh, gw = h // cell, w // cell
        if gh == 0 or gw == 0:
            return None
        grid = mask[: gh * cell, : gw * cell].reshape(gh, cell, gw, cell).sum(axis=(1, 3))
        active = grid >= 6
        if not active.any():
            return None

        seen = np.zeros_like(active, dtype=bool)
        best, best_count = None, 0
        for gy, gx in zip(*np.nonzero(active)):
            if seen[gy, gx]:
                continue
            stack, cells = [(gy, gx)], []
            seen[gy, gx] = True
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < gh and 0 <= nx < gw and active[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            count = sum(int(grid[c]) for c in cells)
            if count > best_count:
                best, best_count = cells, count

        if best is None or best_count < self.min_pixels:
            return None
        ys = [c[0] for c in best]
        xs = [c[1] for c in best]
        return min(xs) * cell, min(ys) * cell, (max(xs) + 1) * cell, (max(ys) + 1) * cell

    def _square_crop_box(self, box, img_w, img_h):
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        side = max(x1 - x0, y1 - y0) * (1 + 2 * self.pad)
        side = min(side, img_w, img_h)
        left = min(max(cx - side / 2, 0), img_w - side)
        top = min(max(cy - side / 2, 0), img_h - side)
        return int(round(left)), int(round(top)), int(round(left + side)), int(round(top + side))


def map_crop_box_to_frame(box_xyxy, crop_box, crop_size):
    """Map a box from resized-crop pixels back to full-frame pixels."""
    cx0, cy0, cx1, cy1 = crop_box
    sx = (cx1 - cx0) / crop_size
    sy = (cy1 - cy0) / crop_size
    x1, y1, x2, y2 = box_xyxy
    return cx0 + x1 * sx, cy0 + y1 * sy, cx0 + x2 * sx, cy0 + y2 * sy


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class WheelDetector:
    """Wraps the trained YOLO model. infer() returns full-frame Detections."""

    def __init__(self, model_path: str, conf_threshold: float = 0.5, imgsz: int = 640,
                 cropper: RedCarCropper | None = None, device: str | None = None):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.imgsz = imgsz
        self.cropper = cropper
        self.device = device
        self.last_crop_box = None  # for the debug overlay

    def infer(self, frame_bgr) -> list[Detection]:
        import cv2

        self.last_crop_box = None
        if self.cropper is not None:
            crop_box = self.cropper.find_crop(frame_bgr)
            if crop_box is None:
                return []  # no car found -> no detection -> WAIT
            x0, y0, x1, y1 = crop_box
            model_input = cv2.resize(frame_bgr[y0:y1, x0:x1], (self.imgsz, self.imgsz),
                                     interpolation=cv2.INTER_LANCZOS4)
            self.last_crop_box = crop_box
        else:
            model_input = frame_bgr

        result = self.model.predict(model_input, conf=self.conf_threshold, imgsz=self.imgsz,
                                    device=self.device, verbose=False)[0]
        names = result.names
        detections = []
        for box in result.boxes:
            xyxy = box.xyxy[0].tolist()
            if self.cropper is not None:
                xyxy = map_crop_box_to_frame(xyxy, crop_box, self.imgsz)
            detections.append(Detection(*xyxy, confidence=float(box.conf),
                                        class_name=names[int(box.cls)]))
        return detections


def best_of_class(detections, class_name):
    """Highest-confidence detection of one class, or None."""
    matches = [d for d in detections if d.class_name == class_name]
    return max(matches, key=lambda d: d.confidence) if matches else None
