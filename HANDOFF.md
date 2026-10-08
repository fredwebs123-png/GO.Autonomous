# GO Autonomous - Project Handoff for Claude Code

AI-guided car wash conveyor positioning system for **GO Car Wash**. A camera watches a vehicle approach the conveyor, an AI model finds the front wheel, the position is converted to real-world inches and smoothed, and a guidance signal (move left / move right / straight / stop) is shown to the driver.

This document contains the project context, current status, decisions made, known issues, a prioritized to-do list, and the **full source of every file** so a Claude Code session can pick up exactly where the chat left off.

---

## 1. Goal and scope

- **End goal:** guide cars onto a car wash conveyor using camera-based vision, with a fail-safe driver-facing signal and, eventually, a stop/engage signal to the conveyor PLC.
- **Current scope: bench prototype.** Single fixed webcam, an RC/toy car as a stand-in vehicle, a marked lane on a desk/floor, and a guidance output. No real conveyor, PLC, or weatherproofing yet.
- **Guidance output is changing:** originally an Arduino + 4 LEDs (built and verified working). The user has now chosen an **on-screen visual avatar** (no voice) on the same computer's monitor as the output for the bench test. Both outputs use the same signal strings, so they can coexist.

## 2. Signal contract (shared by every output)

The state machine emits one of these strings per frame:

| Signal | Meaning |
|---|---|
| `MOVE_LEFT` | Vehicle too far right of centerline; driver should move left |
| `MOVE_RIGHT` | Vehicle too far left; driver should move right |
| `STRAIGHT` | Centered; continue forward |
| `STOP` | Aligned and in stop zone (after N consecutive good frames) |
| `CONVEYOR_MOVING` | Conveyor engaged |
| `WAIT` | No valid detection / fail-safe default |

**Fail-safe principle:** any lost/ambiguous detection must fall back to `WAIT`, never to a "go" signal. Keep this invariant in all changes.

## 3. Pipeline architecture

```
Camera frame
  -> WheelDetector (YOLO, bbox of front wheel)          [STUB - needs trained model]
  -> bottom-center of bbox = ground contact pixel
  -> GroundPlaneCalibrator (homography, pixels -> inches)  [placeholder calibration points]
  -> PositionKalmanFilter x2 (lateral, longitudinal)
  -> GuidanceStateMachine (debounced; N consecutive frames before STOP)
  -> output: Arduino serial  OR  POST http://localhost:8000/update (avatar)
```

Coordinate convention: x = 0 at lane centerline (positive = right), y = 0 at the stop line (longitudinal distance remaining decreases as the car approaches). Units: inches.

## 4. Status

### Done and verified on the user's machine
- Python environment working; all packages installed (`opencv-python`, `numpy`, `ultralytics`, `filterpy`, `pyserial`, plus `torch`/`torchvision`).
- Full skeleton pipeline runs in a loop, printing `state=IDLE signal=WAIT` (correct, since detection is a stub). Camera capture works after the `CAP_DSHOW` fix.
- Arduino LED sign works end to end on **COM6** (Python -> serial -> Arduino -> LEDs), confirmed with the read-back test after re-uploading the sketch.
- Webcam preview works (`camera_preview.py`).

### Written but not yet confirmed by the user
- `camera_capture.py` (frame capture for the dataset). The `frames/` folder is created when the script starts; the user had not run it from the correct folder at last check.
- Avatar server + page. Server tested in the sandbox (serves page, `/status` returns JSON); the visual result in a real browser has not been confirmed.

### Not started
- Dataset collection and labeling (Roboflow, YOLO format, class `front_wheel`).
- YOLO training and wiring the trained model into `WheelDetector.infer()`.
- Real calibration (placeholder points in the code are fake).
- Sending pipeline signals to the avatar (or Arduino) from `main()` - the skeleton currently only prints them.
- Dual-camera path, break-beam backup sensor, PLC/relay integration, safety review.

## 5. User environment

- **OS:** Windows 11, PowerShell (not cmd). Python 3.13 (user-reported `python --version` output), no standalone `pip` on PATH - use `python -m pip ...`.
- **Project folder:** `C:\Users\CurtisHerbsleb\OneDrive - GO Car Wash\Desktop\GO Autonomous` (inside OneDrive - be aware of sync/locking oddities with generated files like `frames/` and model weights).
- **Hardware on hand:** USB webcam (index 0), Arduino Uno on **COM6**, breadboard with 4 LEDs + 220 ohm resistors on pins D2 (left), D3 (right), D4 (stop), D5 (straight), shared ground rail to GND.
- **Not yet available/confirmed:** RC car, calibration markings, NVIDIA GPU (unknown - training may be CPU-only or need Colab).
- The user is non-expert with the terminal: give exact commands, expect screenshots of terminal output, and remember each new PowerShell window starts in the home folder (needs `cd` to the project folder).

## 6. Known issues and gotchas

**Windows / hardware**
- OpenCV default MSMF backend fails with `can't grab frame`; use `cv2.VideoCapture(idx, cv2.CAP_DSHOW)`. Already applied in the preview/capture scripts and in the embedded skeleton below (the user's local skeleton file is named `car_wash_guidance_skeleton (1).py` because of a duplicate download - rename recommended).
- Only one program may hold the COM port: close the Arduino IDE Serial Monitor before running Python.
- Opening the serial port resets the Uno; wait ~2 s before sending, and expect all LEDs to flash briefly on connect (normal reset behavior, not a signal).
- After editing the `.ino`, the sketch must be **re-uploaded** (stale IDE tab caused a false "no echo" result earlier).

**Code**
- `GuidanceStateMachine` has no transition out of `STOPPED`/`CONVEYOR_MOVING` back to `IDLE` when the vehicle leaves, and the Kalman filters are never reset between vehicles. Needs a "vehicle departed" reset.
- `main()` loop uses `time.sleep(1/30)` regardless of processing time; fine for the bench, revisit for real timing.
- `Detection` picks the highest-confidence box with no multi-object tracking/association.
- `filterpy` is installed but unused (the Kalman filter is hand-rolled; either is fine).
- Calibration `image_points` / `world_points` in `main()` are placeholders - **positions are meaningless until real calibration is done.**
- `car_wash_guidance_dual_camera.py`: the imports from the skeleton are commented out and `import cv2` sits under `__main__`, so it will not run as-is. Needs proper imports (refactor shared classes into a module).
- Dual camera frame sync, and doubled inference load on a single Jetson, are untested concerns.

## 7. Key design decisions (and why)

- **Detect the front wheel contact point**, not the whole car - it's what must land on the conveyor track. Fallback: bottom-center of a whole-vehicle box.
- **Homography calibration first** - bad calibration makes a perfect detector give wrong positions; debug calibration before blaming the model.
- **Debounce before STOP** (5 consecutive frames) and **fail to WAIT** on any invalid detection.
- **Camera-only is acceptable for the bench**; for real deployment keep at least one independent non-vision fail-safe (photoelectric/break-beam) at the stop trigger, or use two cameras with a fusion/agreement check.
- **Avatar output uses a local HTTP server + polling page** (stdlib only, no new pip packages) so the guidance code just POSTs the same signal strings it used to send over serial.
- Production-path hardware discussed: NVIDIA Jetson Orin Nano Super (~$249 list), IP66 PoE camera, NEMA enclosure, relay to the conveyor PLC; machine-safety review (e.g. ISO 13849) before any live deployment.

## 8. Prioritized next steps for Claude Code

1. **Tidy the project folder:** rename `car_wash_guidance_skeleton (1).py` to `car_wash_guidance_skeleton.py`; consider refactoring shared classes (`GroundPlaneCalibrator`, `PositionKalmanFilter`, `GuidanceStateMachine`, `Detection`, `WheelDetector`) into a `carwash/` module so the single- and dual-camera scripts import them cleanly.
2. **Verify the avatar:** run `python avatar_server.py`, open `http://localhost:8000`, confirm each pose renders; polish visuals if desired.
3. **Add an output abstraction** in the pipeline: a small `send_signal(signal)` that can drive the avatar (HTTP POST, with a short timeout and error handling so a dead server never crashes the loop) and optionally the Arduino (serial), selected by a config flag. Set `RUN_DEMO = False` in `avatar_server.py` when driven by the pipeline.
4. **Add a live debug overlay** to the main pipeline (draw detection box, calibrated position, state, signal on the camera window) - this makes calibration and tuning far easier.
5. **Build a calibration helper:** click points on a camera frame, enter measured inches, save to a JSON config, and verify with a held-out test point. Load it in the pipeline instead of hardcoded values.
6. **Dataset collection:** run `camera_capture.py` while moving the RC car through the lane (aim 300-500 varied frames), then label in Roboflow (class `front_wheel`), export YOLOv8 format.
7. **Train** (`yolo detect train data=<path>\data.yaml model=yolov8n.pt epochs=100 imgsz=640`) - check for a GPU first (`python -c "import torch; print(torch.cuda.is_available())"`), otherwise use Colab - then implement `WheelDetector.infer()` with the trained `best.pt`.
8. **Fix state machine reset** (vehicle departed -> `IDLE`, reset Kalman filters) and add simple unit tests for the state machine (fail-safe on lost detection, debounce, tolerance edges). These need no hardware.
9. Later: dual-camera fusion, break-beam fail-safe, PLC/relay output, Jetson deployment.

## 9. Suggested opening prompt for Claude Code

> I'm continuing a project called GO Autonomous (camera-guided car wash conveyor positioning). Read `HANDOFF.md` in this folder for full context. Start with next steps 1-3: tidy the folder, verify the avatar works, then add an output abstraction so the main pipeline can drive the avatar (and optionally the Arduino on COM6). I'm on Windows 11 with PowerShell; the camera needs `cv2.CAP_DSHOW`.

## 10. Related deliverables (not embedded here)

Created earlier in the chat as separate files: `GO_Autonomous_Gantt_Chart.xlsx` (52-week Gantt with phases and steps), `car_wash_full_launch_project_plan.docx` (8-phase prototype-to-launch plan), `car_wash_guidance_project_plan.docx` / `.md` (bench-prototype plan with hardware list and setup steps).

## 11. How to run each piece (Windows PowerShell, from the project folder)

```powershell
python -m pip install -r requirements.txt
python camera_preview.py          # live camera, press q to quit
python camera_capture.py          # live camera, press s to save frame, q to quit
python test_arduino_leds.py       # cycles all LED signals (close Serial Monitor first)
python avatar_server.py           # then open http://localhost:8000
python car_wash_guidance_skeleton.py   # full pipeline loop (detection is a stub)
```

---

## Appendix: full source


### `requirements.txt`

Python dependencies (all confirmed installed on the user's machine)

```text
opencv-python
numpy
ultralytics
filterpy
pyserial
```


### `car_wash_guidance_skeleton.py`

Main single-camera pipeline: calibration, detection stub, Kalman tracking, state machine. **Runs end-to-end but detection is a stub.** (Embedded copy includes the CAP_DSHOW camera fix the user applied locally.)

```python
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

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # CAP_DSHOW fixes MSMF 'can't grab frame' error on Windows; TODO: camera source / RTSP stream

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
```


### `car_wash_guidance_dual_camera.py`

Two-camera variant with fusion layer. **Not runnable standalone yet** - see known issues.

```python
"""
Car Wash Vehicle Guidance System - DUAL CAMERA Prototype Skeleton
===================================================================

Extends the single-camera pipeline to run two cameras at different angles,
each with its own calibration and tracking, fused together before being
handed to the guidance state machine. This gets you sensor redundancy
without a break-beam sensor -- if the two cameras disagree or one loses
detection, the system falls back to a conservative "wait" state rather
than trusting a single, possibly-wrong, camera.

Reuses: GroundPlaneCalibrator, WheelDetector, PositionKalmanFilter,
GuidanceStateMachine from the single-camera skeleton (import or paste them
in above this point).
"""

import time
from dataclasses import dataclass

# from car_wash_guidance_skeleton import (
#     GroundPlaneCalibrator, WheelDetector, PositionKalmanFilter, GuidanceStateMachine
# )


@dataclass
class CameraEstimate:
    lateral_in: float | None
    longitudinal_in: float | None
    confidence: float  # detector confidence, 0.0 if no detection this frame
    valid: bool


class CameraPipeline:
    """
    Wraps one camera's full chain: capture -> detect -> calibrate -> smooth.
    Instantiate one of these per physical camera.
    """

    def __init__(self, camera_source, model_path: str, calibrator, dt: float = 1 / 30.0):
        self.cap_source = camera_source          # e.g. a cv2.VideoCapture index or RTSP URL
        self.detector = WheelDetector(model_path)
        self.calibrator = calibrator              # this camera's own GroundPlaneCalibrator
        self.lateral_kf = PositionKalmanFilter(dt=dt)
        self.longitudinal_kf = PositionKalmanFilter(dt=dt)

    def process_frame(self, frame) -> CameraEstimate:
        try:
            detections = self.detector.infer(frame)
        except NotImplementedError:
            detections = []

        if not detections:
            return CameraEstimate(None, None, confidence=0.0, valid=False)

        best = max(detections, key=lambda d: d.confidence)
        px, py = best.ground_contact_pixel()
        world_x, world_y = self.calibrator.pixel_to_world(px, py)

        self.lateral_kf.predict()
        self.lateral_kf.update(world_x)
        self.longitudinal_kf.predict()
        self.longitudinal_kf.update(world_y)

        return CameraEstimate(
            lateral_in=self.lateral_kf.position,
            longitudinal_in=self.longitudinal_kf.position,
            confidence=best.confidence,
            valid=True,
        )


# ---------------------------------------------------------------------------
# FUSION LAYER -- the genuinely new piece vs. the single-camera version
# ---------------------------------------------------------------------------

class DualCameraFusion:
    """
    Reconciles two CameraEstimates into one trusted estimate for the state
    machine. This is where the redundancy benefit actually comes from --
    without this logic, two cameras is just two independent single-camera
    systems bolted together.
    """

    def __init__(self, agreement_tolerance_in: float = 4.0):
        self.agreement_tolerance_in = agreement_tolerance_in

    def fuse(self, est_a: CameraEstimate, est_b: CameraEstimate):
        """
        Returns (lateral_offset, longitudinal_dist, detection_valid) for the
        state machine, exactly matching the single-camera pipeline's contract.
        """
        # Both cameras lost the vehicle -> unambiguous fail-safe
        if not est_a.valid and not est_b.valid:
            return None, None, False

        # Only one camera sees it: usable, but treat as lower-confidence.
        # (Simplest policy: use it. Stricter policy: require both for STOP-zone
        # decisions specifically -- add that check in the state machine caller.)
        if est_a.valid and not est_b.valid:
            return est_a.lateral_in, est_a.longitudinal_in, True
        if est_b.valid and not est_a.valid:
            return est_b.lateral_in, est_b.longitudinal_in, True

        # Both cameras see it -- check agreement
        lateral_diff = abs(est_a.lateral_in - est_b.lateral_in)
        longitudinal_diff = abs(est_a.longitudinal_in - est_b.longitudinal_in)

        if lateral_diff > self.agreement_tolerance_in or longitudinal_diff > self.agreement_tolerance_in:
            # Cameras disagree meaningfully -- something is wrong (occlusion,
            # false detection, miscalibration). Fail safe rather than guess.
            return None, None, False

        # Agreement -- average them, weighted by confidence
        total_conf = est_a.confidence + est_b.confidence
        w_a = est_a.confidence / total_conf
        w_b = est_b.confidence / total_conf

        fused_lateral = est_a.lateral_in * w_a + est_b.lateral_in * w_b
        fused_longitudinal = est_a.longitudinal_in * w_a + est_b.longitudinal_in * w_b

        return fused_lateral, fused_longitudinal, True


# ---------------------------------------------------------------------------
# MAIN LOOP -- dual camera version
# ---------------------------------------------------------------------------

def main():
    # --- one-time setup: each camera gets its OWN calibration, same world coords ---
    calib_a = GroundPlaneCalibrator(
        image_points=[(120, 400), (520, 400), (80, 600), (560, 600)],  # TODO: camera A's measured points
        world_points=[(-24, 120), (24, 120), (-30, 40), (30, 40)],
    )
    calib_b = GroundPlaneCalibrator(
        image_points=[(90, 380), (540, 390), (60, 610), (580, 615)],   # TODO: camera B's measured points
        world_points=[(-24, 120), (24, 120), (-30, 40), (30, 40)],      # SAME real-world targets as camera A
    )

    pipeline_a = CameraPipeline(camera_source=0, model_path="front_wheel_best.pt", calibrator=calib_a)
    pipeline_b = CameraPipeline(camera_source=1, model_path="front_wheel_best.pt", calibrator=calib_b)

    fusion = DualCameraFusion(agreement_tolerance_in=4.0)
    fsm = GuidanceStateMachine()

    cap_a = cv2.VideoCapture(pipeline_a.cap_source)
    cap_b = cv2.VideoCapture(pipeline_b.cap_source)

    try:
        while True:
            ret_a, frame_a = cap_a.read()
            ret_b, frame_b = cap_b.read()
            if not ret_a or not ret_b:
                break

            est_a = pipeline_a.process_frame(frame_a)
            est_b = pipeline_b.process_frame(frame_b)

            lateral_offset, longitudinal_dist, detection_valid = fusion.fuse(est_a, est_b)

            state, signal = fsm.update(lateral_offset, longitudinal_dist, detection_valid)

            # TODO: send `signal` to LED sign (see carwash_led_sign.ino)
            # TODO: when state == GuidanceState.STOPPED, call fsm.engage_conveyor()

            print(f"state={state.name:20s} signal={signal:12s} "
                  f"lateral={lateral_offset} longitudinal={longitudinal_dist}")

            time.sleep(1 / 30.0)

    finally:
        cap_a.release()
        cap_b.release()


if __name__ == "__main__":
    import cv2  # placed here since it's only needed in main() for this skeleton
    main()
```


### `carwash_led_sign.ino`

Arduino sketch for the physical LED sign (includes serial echo debug line). Working.

```cpp
/*
  Car Wash Guidance LED Sign
  ---------------------------
  Receives simple string commands over USB serial from the Python pipeline
  and drives left/right/stop LEDs accordingly.

  Wiring (adjust pins to match your build):
    LEFT_LED  -> pin 2 (through ~220 ohm resistor to GND)
    RIGHT_LED -> pin 3 (through ~220 ohm resistor to GND)
    STOP_LED  -> pin 4 (through ~220 ohm resistor to GND)
    (Optional) STRAIGHT_LED -> pin 5

  Python side sends one of: MOVE_LEFT, MOVE_RIGHT, STRAIGHT, STOP,
  CONVEYOR_MOVING, WAIT  -- each terminated with a newline.
*/

const int LEFT_PIN = 2;
const int RIGHT_PIN = 3;
const int STOP_PIN = 4;
const int STRAIGHT_PIN = 5;

// Simple blink state for the STOP light (more attention-grabbing than solid on)
unsigned long lastBlinkTime = 0;
bool blinkState = false;
const unsigned long BLINK_INTERVAL_MS = 400;

String currentSignal = "WAIT";

void setup() {
  pinMode(LEFT_PIN, OUTPUT);
  pinMode(RIGHT_PIN, OUTPUT);
  pinMode(STOP_PIN, OUTPUT);
  pinMode(STRAIGHT_PIN, OUTPUT);

  allOff();
  Serial.begin(9600);
  Serial.setTimeout(50);
}

void loop() {
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();
    if (incoming.length() > 0) {
      currentSignal = incoming;
      Serial.print("Received: ");
      Serial.println(currentSignal);
    }
  }

  applySignal(currentSignal);
}

void allOff() {
  digitalWrite(LEFT_PIN, LOW);
  digitalWrite(RIGHT_PIN, LOW);
  digitalWrite(STOP_PIN, LOW);
  digitalWrite(STRAIGHT_PIN, LOW);
}

void applySignal(const String &signal) {
  if (signal == "MOVE_LEFT") {
    allOff();
    digitalWrite(LEFT_PIN, HIGH);

  } else if (signal == "MOVE_RIGHT") {
    allOff();
    digitalWrite(RIGHT_PIN, HIGH);

  } else if (signal == "STRAIGHT") {
    allOff();
    digitalWrite(STRAIGHT_PIN, HIGH);

  } else if (signal == "STOP") {
    // Blink the stop LED so it's more attention-grabbing than a solid light
    digitalWrite(LEFT_PIN, LOW);
    digitalWrite(RIGHT_PIN, LOW);
    digitalWrite(STRAIGHT_PIN, LOW);

    if (millis() - lastBlinkTime >= BLINK_INTERVAL_MS) {
      blinkState = !blinkState;
      lastBlinkTime = millis();
    }
    digitalWrite(STOP_PIN, blinkState ? HIGH : LOW);

  } else if (signal == "CONVEYOR_MOVING") {
    allOff();
    digitalWrite(STOP_PIN, HIGH); // solid stop light while moving through

  } else { // "WAIT" or anything unrecognized -> fail-safe: no "go" signals
    allOff();
  }
}
```


### `test_arduino_leds.py`

Standalone LED/serial test with Arduino read-back. Working on COM6.

```python
"""
Standalone Arduino/LED test - confirms the serial connection and LED sign
work correctly, independent of the camera/vision pipeline.
"""

import serial
import time

# TODO: change this to match your Arduino's port from the Arduino IDE (Tools > Port)
PORT = "COM6"
BAUD_RATE = 9600

print(f"Connecting to Arduino on {PORT}...")
arduino = serial.Serial(PORT, BAUD_RATE)
time.sleep(2)  # give the Arduino a moment after the serial connection resets it
print("Connected. Running through each signal...")

signals = ["MOVE_LEFT", "MOVE_RIGHT", "STRAIGHT", "STOP", "CONVEYOR_MOVING", "WAIT"]

for signal in signals:
    print(f"Sending: {signal}")
    arduino.write((signal + "\n").encode())
    time.sleep(0.3)
    while arduino.in_waiting:
        print("  Arduino says:", arduino.readline().decode(errors="replace").strip())
    time.sleep(2.7)  # remainder of the 3-second pause so you can see each LED state

print("Test complete. All LEDs should have lit up in sequence.")
arduino.close()
```


### `camera_preview.py`

Live webcam preview window. Working.

```python
"""
Standalone camera preview - shows the live webcam feed in a window so you can
check framing, positioning, and plan your calibration reference points.

Press 'q' in the video window to quit.
"""

import cv2

CAMERA_INDEX = 0  # change to 1, 2, etc. if this doesn't open the right camera

print("Opening camera...")
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW per your earlier fix on Windows

if not cap.isOpened():
    print("Could not open camera. Try changing CAMERA_INDEX to 1 or 2.")
else:
    print("Camera opened. Press 'q' in the video window to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        cv2.imshow("Camera Preview - press 'q' to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed.")
```


### `camera_capture.py`

Live preview + press `s` to save frames to `frames/` for labeling. Written, not yet confirmed run by user.

```python
"""
Camera preview + frame capture - shows the live webcam feed and lets you
save the current frame to disk with a single keypress. Use this while
driving the RC car through your lane to build up a labeling dataset
without needing to record and extract from a separate video file.

Controls (with the video window focused):
  's' - save the current frame to the 'frames' folder
  'q' - quit
"""

import cv2
import os

CAMERA_INDEX = 0  # change to 1, 2, etc. if this doesn't open the right camera
OUTPUT_DIR = "frames"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Opening camera...")
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("Could not open camera. Try changing CAMERA_INDEX to 1 or 2.")
else:
    print("Camera opened.")
    print("  Press 's' to save the current frame")
    print("  Press 'q' to quit")

    saved_count = 0
    # Start the counter above any files already in the folder, so repeated
    # sessions don't overwrite earlier captures.
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("frame_") and f.endswith(".jpg")]
    if existing:
        saved_count = max(int(f[6:10]) for f in existing) + 1

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        display_frame = frame.copy()
        cv2.putText(display_frame, f"Saved: {saved_count}  (press 's' to save, 'q' to quit)",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Camera Capture", display_frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            filename = os.path.join(OUTPUT_DIR, f"frame_{saved_count:04d}.jpg")
            cv2.imwrite(filename, frame)  # save the clean frame, without the on-screen text
            print(f"Saved {filename}")
            saved_count += 1

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {saved_count} frames total saved in the '{OUTPUT_DIR}' folder.")
```


### `extract_frames.py`

Extract frames from a recorded video (alternative to camera_capture.py).

```python
"""
Extracts individual frames from a recorded video file, for use in labeling
a training dataset. Saves roughly 2 frames per second by default -- enough
variety without ending up with thousands of near-duplicate images.
"""

import cv2
import os

VIDEO_PATH = "your_video.mp4"   # TODO: change to your actual video filename
OUTPUT_DIR = "frames"
FRAMES_PER_SECOND_TO_SAVE = 2    # lower = fewer, more varied frames

os.makedirs(OUTPUT_DIR, exist_ok=True)

cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"Could not open {VIDEO_PATH}. Check the filename/path.")
else:
    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_interval = max(1, round(source_fps / FRAMES_PER_SECOND_TO_SAVE))

    frame_count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            filename = os.path.join(OUTPUT_DIR, f"frame_{saved_count:04d}.jpg")
            cv2.imwrite(filename, frame)
            saved_count += 1

        frame_count += 1

    cap.release()
    print(f"Done. Saved {saved_count} frames to the '{OUTPUT_DIR}' folder.")
```


### `avatar_server.py`

Local HTTP server for the on-screen avatar guidance output (stdlib only). Tested server-side; user has not confirmed visual result yet.

```python
"""
Avatar guidance server - serves the avatar_display.html page and exposes a
tiny local API for updating what it shows. Replaces the Arduino/LED sign
as the guidance output: instead of lighting an LED, the pipeline sends the
same signal strings (MOVE_LEFT, STOP, etc.) to this server, and the avatar
on your monitor updates in real time.

Usage:
  1. Run this script: python avatar_server.py
  2. Open a browser to: http://localhost:8000
  3. By default it runs a demo loop cycling through signals every 3 seconds,
     so you can confirm the avatar works before wiring in the real pipeline.
     Set RUN_DEMO = False once you're ready to drive it from your own code.

To send a signal from other code (e.g. the guidance state machine), do:
  import requests
  requests.post("http://localhost:8000/update", json={"signal": "MOVE_LEFT"})
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RUN_DEMO = True
PORT = 8000
HTML_FILE = "avatar_display.html"

current_signal = "WAIT"
lock = threading.Lock()


class AvatarHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet the default request logging

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/status":
            self._serve_status()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/update":
            self._handle_update()
        else:
            self.send_error(404)

    def _serve_html(self):
        try:
            with open(HTML_FILE, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(500, f"{HTML_FILE} not found next to this script")

    def _serve_status(self):
        with lock:
            payload = json.dumps({"signal": current_signal}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_update(self):
        global current_signal
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            with lock:
                current_signal = data.get("signal", current_signal)
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            self.send_error(400, str(e))


def run_demo():
    """Cycles through every signal so you can confirm the avatar works standalone."""
    global current_signal
    demo_signals = ["MOVE_LEFT", "MOVE_RIGHT", "STRAIGHT", "STOP", "CONVEYOR_MOVING", "WAIT"]
    time.sleep(2)  # give you a moment to open the browser tab first
    while True:
        for signal in demo_signals:
            with lock:
                current_signal = signal
            print(f"Demo: showing {signal}")
            time.sleep(3)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("localhost", PORT), AvatarHandler)
    print(f"Avatar server running at http://localhost:{PORT}")
    print("Open that address in your browser to see the avatar.")

    if RUN_DEMO:
        print("Demo mode ON - cycling through signals automatically every 3 seconds.")
        threading.Thread(target=run_demo, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
```


### `avatar_display.html`

Avatar webpage (SVG avatar, polls `/status` every 300 ms).

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>GO Autonomous - Guidance Avatar</title>
<style>
  body {
    margin: 0;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: #14181c;
    font-family: Arial, Helvetica, sans-serif;
    color: white;
    overflow: hidden;
  }
  #avatar-wrap {
    width: 320px;
    height: 320px;
    transition: transform 0.25s ease;
  }
  #label {
    margin-top: 30px;
    font-size: 48px;
    font-weight: bold;
    letter-spacing: 2px;
    text-align: center;
    min-height: 60px;
  }
  .lean-left  { transform: rotate(-8deg) translateX(-20px); }
  .lean-right { transform: rotate(8deg) translateX(20px); }
  .pulse { animation: pulse 0.5s infinite alternate; }
  @keyframes pulse {
    from { transform: scale(1); }
    to   { transform: scale(1.06); }
  }
  #arrow {
    transition: opacity 0.2s ease;
  }
</style>
</head>
<body>

<div id="avatar-wrap">
  <svg viewBox="0 0 200 200" width="320" height="320">
    <!-- body -->
    <circle cx="100" cy="120" r="55" fill="#3A7CA5"/>
    <!-- head -->
    <circle cx="100" cy="55" r="38" fill="#F4C89B"/>
    <!-- eyes -->
    <circle cx="87" cy="50" r="5" fill="#222"/>
    <circle cx="113" cy="50" r="5" fill="#222"/>
    <!-- mouth (neutral, overwritten by JS for stop = flat, go = smile) -->
    <path id="mouth" d="M85 68 Q100 78 115 68" stroke="#222" stroke-width="3" fill="none" stroke-linecap="round"/>
    <!-- arm indicating direction -->
    <g id="arrow">
      <polygon points="100,150 130,175 70,175" fill="#FFD447"/>
    </g>
  </svg>
</div>

<div id="label">Waiting...</div>

<script>
async function poll() {
  try {
    const res = await fetch('/status');
    const data = await res.json();
    applySignal(data.signal);
  } catch (e) {
    document.getElementById('label').innerText = "Connecting...";
  }
  setTimeout(poll, 300);
}

function applySignal(signal) {
  const wrap = document.getElementById('avatar-wrap');
  const label = document.getElementById('label');
  const mouth = document.getElementById('mouth');
  const arrow = document.getElementById('arrow');

  wrap.className = "";
  arrow.style.opacity = 1;
  mouth.setAttribute('d', 'M85 68 Q100 78 115 68'); // default smile-ish

  switch (signal) {
    case "MOVE_LEFT":
      wrap.className = "lean-left";
      label.innerText = "\u2190 MOVE LEFT";
      arrow.setAttribute('transform', 'rotate(-90 100 160)');
      break;
    case "MOVE_RIGHT":
      wrap.className = "lean-right";
      label.innerText = "MOVE RIGHT \u2192";
      arrow.setAttribute('transform', 'rotate(90 100 160)');
      break;
    case "STRAIGHT":
      label.innerText = "STRAIGHT AHEAD";
      arrow.setAttribute('transform', '');
      break;
    case "STOP":
      wrap.className = "pulse";
      label.innerText = "STOP";
      mouth.setAttribute('d', 'M85 70 L115 70'); // flat mouth
      arrow.style.opacity = 0;
      break;
    case "CONVEYOR_MOVING":
      label.innerText = "ENJOY YOUR WASH!";
      arrow.style.opacity = 0;
      break;
    default:
      label.innerText = "Waiting...";
      arrow.style.opacity = 0;
  }
}

poll();
</script>

</body>
</html>
```
