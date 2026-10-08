"""Ground-plane calibration: image pixels -> real-world inches (homography).

Calibration file format (JSON, written by calibrate.py):
    {
      "image_points": [[px, py], ...],     # 4+ pixel points clicked on a camera frame
      "world_points": [[x_in, y_in], ...], # same points measured on the ground
      "placeholder": false                 # true = fake numbers, positions meaningless
    }
World coords: x = 0 at the track centerline, +x = driver's right facing into
the tunnel; y = 0 at the stop line, +y = toward the approaching car.
"""

import json
from pathlib import Path

import numpy as np


class GroundPlaneCalibrator:
    def __init__(self, image_points, world_points, placeholder: bool = False):
        import cv2

        if len(image_points) < 4 or len(image_points) != len(world_points):
            raise ValueError("Need at least 4 matching image/world point pairs")
        self.image_points = np.array(image_points, dtype=np.float64)
        self.world_points = np.array(world_points, dtype=np.float64)
        self.placeholder = placeholder
        self.H, _ = cv2.findHomography(self.image_points, self.world_points)
        if self.H is None:
            raise ValueError("Homography failed - points may be collinear or duplicated")

    @classmethod
    def from_json(cls, path):
        data = json.loads(Path(path).read_text())
        return cls(data["image_points"], data["world_points"], data.get("placeholder", False))

    def to_json(self, path, extra: dict | None = None):
        data = {
            "image_points": self.image_points.tolist(),
            "world_points": self.world_points.tolist(),
            "placeholder": self.placeholder,
        }
        if extra:
            data.update(extra)
        Path(path).write_text(json.dumps(data, indent=2))

    def pixel_to_world(self, px, py):
        """Convert one pixel coordinate to (x_inches, y_inches) on the ground."""
        mapped = self.H @ np.array([px, py, 1.0])
        mapped /= mapped[2]
        return float(mapped[0]), float(mapped[1])

    def reprojection_errors(self):
        """Inches of error at each calibration point (should be well under 1 in)."""
        errs = []
        for (px, py), (wx, wy) in zip(self.image_points, self.world_points):
            x, y = self.pixel_to_world(px, py)
            errs.append(float(np.hypot(x - wx, y - wy)))
        return errs
