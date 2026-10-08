"""
Car Wash Vehicle Guidance System - Prototype Skeleton
=======================================================

This skeleton demonstrates the full pipeline:
  1. Camera -> ground-plane calibration (homography)
  2. Detection (placeholder for YOLO model)
  3. Kalman filter tracking (position + velocity, smoothed)
  4. Real-world offset computation (lateral + longitudinal)
  5. State machine driving guidance output (left/right/stop/engage)

Fill in the marked TODOs with your actual model/hardware calls.
Dependencies: opencv-python, numpy, ultralytics (for real YOLO), filterpy (optional)
"""

import time
import numpy as np
import cv2
from dataclasses import dataclass
from enum import Enum, auto


# ---------------------------------------------------------------------------
# 1. CAMERA CALIBRATION (Homography: image pixels -> real-world ground coords)
# ---------------------------------------------------------------------------

class GroundPlaneCalibrator:
    """
    Maps image pixel coordinates to real-world ground coordinates (inches),
    using 4+ known correspondence points marked on the floor during install.
    """

    def __init__(self, image_points, world_points):
        """
        image_points: list of (px, py) pixel coords, e.g. from a calibration photo
        world_points: corresponding list of (x_inches, y_inches) real-world coords,
                      with x=0 at lane centerline, y=0 at the target stop line
        """
        img_pts = np.array(image_points, dtype=np.float32)
        world_pts = np.array(world_points, dtype=np.float32)
        self.H, _ = cv2.findHomography(img_pts, world_pts)

    def pixel_to_world(self, px, py):
        """Convert a single pixel coordinate to (x_inches, y_inches) on the ground."""
        pt = np.array([px, py, 1.0], dtype=np.float32)
        mapped = self.H @ pt
        mapped /= mapped[2]  # normalize homogeneous coordinate
        return float(mapped[0]), float(mapped[1])


# ---------------------------------------------------------------------------
# 2. DETECTION (placeholder — swap in your trained YOLO model)
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str  # e.g. "front_wheel"

    def ground_contact_pixel(self):
        """Bottom-center of bounding box — approximates the wheel/ground contact point."""
        cx = (self.x1 + self.x2) / 2.0
        cy = self.y2
        return cx, cy


class WheelDetector:
    """
    Wraps your trained detection model. Replace `infer` with a real call, e.g.:
        from ultralytics import YOLO
        self.model = YOLO("front_wheel_best.pt")
        results = self.model(frame)[0]
    """

    def __init__(self, model_path: str, conf_threshold: float = 0.5):
        self.conf_threshold = conf_threshold
        # TODO: load your real model here
        # self.model = YOLO(model_path)

    def infer(self, frame) -> list[Detection]:
        # TODO: replace with real inference, filter by confidence,
        # and return only the "front_wheel" class detections.
        raise NotImplementedError("Wire up your YOLO model here")


# ---------------------------------------------------------------------------
# 3. KALMAN FILTER TRACKING (smooths position, estimates velocity)
# ---------------------------------------------------------------------------

class PositionKalmanFilter:
    """
    Simple constant-velocity Kalman filter tracking 1D ground position (e.g. y,
    the longitudinal distance to the stop line). Run a second independent
    instance for the lateral (x) axis if you want smoothed velocity there too.

    State vector: [position, velocity]
    """

    def __init__(self, dt: float, process_noise: float = 1.0, measurement_noise: float = 4.0):
        self.dt = dt

        # State transition matrix: position updates by velocity * dt
        self.F = np.array([[1, dt],
                            [0, 1]])

        # We only measure position directly
        self.H = np.array([[1, 0]])

        # Process noise covariance (tune based on how erratically cars move)
        q = process_noise
        self.Q = np.array([[dt**4 / 4, dt**3 / 2],
                            [dt**3 / 2, dt**2]]) * q

        # Measurement noise (tune based on detector jitter)
        self.R = np.array([[measurement_noise]])

        self.P = np.eye(2) * 500.0  # initial uncertainty
        self.x = np.array([[0.0], [0.0]])  # [position, velocity]
        self.initialized = False

    def reset(self, initial_position: float):
        self.x = np.array([[initial_position], [0.0]])
        self.P = np.eye(2) * 500.0
        self.initialized = True

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, measurement: float):
        if not self.initialized:
            self.reset(measurement)
            return self.x

        z = np.array([[measurement]])
        y = z - (self.H @ self.x)                     # innovation
        S = self.H @ self.P @ self.H.T + self.R        # innovation covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)       # Kalman gain

        self.x = self.x + K @ y
        self.P = (np.eye(2) - K @ self.H) @ self.P
        return self.x

    @property
    def position(self) -> float:
        return float(self.x[0, 0])

    @property
    def velocity(self) -> float:
        return float(self.x[1, 0])


# ---------------------------------------------------------------------------
# 4. STATE MACHINE
# ---------------------------------------------------------------------------

class GuidanceState(Enum):
    IDLE = auto()
    VEHICLE_DETECTED = auto()
    GUIDING = auto()
    ALIGNED = auto()
    STOPPED = auto()
    CONVEYOR_ENGAGED = auto()


class GuidanceStateMachine:
    def __init__(self, lateral_tolerance_in: float = 3.0, stop_zone_in: float = 6.0,
                 required_consecutive_frames: int = 5):
        self.state = GuidanceState.IDLE
        self.lateral_tolerance_in = lateral_tolerance_in
        self.stop_zone_in = stop_zone_in
        self.required_consecutive_frames = required_consecutive_frames
        self._aligned_streak = 0

    def update(self, lateral_offset_in: float, longitudinal_dist_in: float, detection_valid: bool):
        """
        lateral_offset_in: + = too far right, - = too far left, 0 = centered
        longitudinal_dist_in: distance remaining to the stop line (decreasing as car approaches)
        detection_valid: False if detector lost track / low confidence this frame
        """
        if not detection_valid:
            # Fail-safe: any ambiguity drops us back to a safe waiting state
            self._aligned_streak = 0
            if self.state not in (GuidanceState.IDLE, GuidanceState.CONVEYOR_ENGAGED):
                self.state = GuidanceState.VEHICLE_DETECTED
            return self.state, self._guidance_signal(lateral_offset_in, longitudinal_dist_in=None)

        if self.state == GuidanceState.IDLE:
            self.state = GuidanceState.VEHICLE_DETECTED

        if self.state in (GuidanceState.VEHICLE_DETECTED, GuidanceState.GUIDING, GuidanceState.ALIGNED):
            is_centered = abs(lateral_offset_in) <= self.lateral_tolerance_in
            in_stop_zone = longitudinal_dist_in <= self.stop_zone_in

            if is_centered and in_stop_zone:
                self._aligned_streak += 1
            else:
                self._aligned_streak = 0
                self.state = GuidanceState.GUIDING

            if self._aligned_streak >= self.required_consecutive_frames:
                self.state = GuidanceState.STOPPED

        signal = self._guidance_signal(lateral_offset_in, longitudinal_dist_in)
        return self.state, signal

    def engage_conveyor(self):
        if self.state == GuidanceState.STOPPED:
            self.state = GuidanceState.CONVEYOR_ENGAGED
            return True
        return False

    def _guidance_signal(self, lateral_offset_in, longitudinal_dist_in):
        """Translate state + offsets into a driver-facing instruction."""
        if self.state == GuidanceState.STOPPED:
            return "STOP"
        if self.state == GuidanceState.CONVEYOR_ENGAGED:
            return "CONVEYOR_MOVING"
        if lateral_offset_in is None:
            return "WAIT"  # lost detection
        if lateral_offset_in > self.lateral_tolerance_in:
            return "MOVE_LEFT"
        if lateral_offset_in < -self.lateral_tolerance_in:
            return "MOVE_RIGHT"
        return "STRAIGHT"


# ---------------------------------------------------------------------------
# 5. MAIN LOOP (wiring it all together)
# ---------------------------------------------------------------------------

def main():
    # --- one-time setup, done at install time ---
    calib = GroundPlaneCalibrator(
        image_points=[(120, 400), (520, 400), (80, 600), (560, 600)],   # TODO: your measured pixel points
        world_points=[(-24, 120), (24, 120), (-30, 40), (30, 40)],       # TODO: your measured inches
    )

    detector = WheelDetector(model_path="front_wheel_best.pt")
    lateral_kf = PositionKalmanFilter(dt=1 / 30.0)
    longitudinal_kf = PositionKalmanFilter(dt=1 / 30.0)
    fsm = GuidanceStateMachine()

    cap = cv2.VideoCapture(0)  # TODO: your camera source / RTSP stream

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detections = []
            try:
                detections = detector.infer(frame)
            except NotImplementedError:
                pass  # model not wired up yet in this skeleton

            detection_valid = len(detections) > 0

            if detection_valid:
                # Pick highest-confidence detection (add tracking/association for multi-object scenes)
                best = max(detections, key=lambda d: d.confidence)
                px, py = best.ground_contact_pixel()
                world_x, world_y = calib.pixel_to_world(px, py)

                lateral_kf.predict()
                lateral_kf.update(world_x)
                longitudinal_kf.predict()
                longitudinal_kf.update(world_y)

                lateral_offset = lateral_kf.position
                longitudinal_dist = longitudinal_kf.position
            else:
                lateral_offset, longitudinal_dist = None, None

            state, signal = fsm.update(lateral_offset, longitudinal_dist, detection_valid)

            # TODO: send `signal` to your physical sign/light controller (serial, GPIO, MQTT, etc.)
            # TODO: when state == GuidanceState.STOPPED, trigger fsm.engage_conveyor()
            #       and send the actual conveyor-start signal to your PLC/relay.

            print(f"state={state.name:20s} signal={signal:12s} "
                  f"lateral={lateral_offset} longitudinal={longitudinal_dist}")

            time.sleep(1 / 30.0)  # match your camera frame rate

    finally:
        cap.release()


if __name__ == "__main__":
    main()
