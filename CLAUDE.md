# GO Autonomous - context for Claude Code

Camera-guided car wash conveyor positioning for GO Car Wash ("Self Loading Program").
A camera finds the driver-side front tire, converts it to inches on the ground,
smooths it, and tells the driver TURN WHEEL LEFT / RIGHT / STRAIGHT / STOP via an
on-screen mascot (Miles) and optionally an Arduino LED sign.

User: Fred Weber (GO Car Wash). Not a terminal expert - give exact PowerShell commands,
one per code block, and expect screenshots. Windows 11.

## Status (2026-10-07)
- **Bench mock-up works end to end** with a red toy car on a paper mat: detection,
  calibration (`config/calibration_bench.json`), guidance, Miles avatar, conveyor simulation.
- **The toy is throwaway.** Goal is full-scale: real cars, real tunnel entrance. Keep code
  scale-independent (everything site-specific lives in `config/`).
- **Next big step:** collect real footage at a site (Phase 1 hardware: 2 PoE cameras - side view
  of driver-side tires + overhead/front; mini PC recorder). Parts/Amazon list was drafted in chat,
  not committed. IT must approve camera brands. Then label real tires and retrain.
- Phase 2 (later): live advisory pilot. **Never** drive the conveyor/PLC until a machine-safety
  review (ISO 13849) with the conveyor vendor - advisory only.

## Architecture
`run_guidance.py`: frame -> `carwash.detection.WheelDetector` (YOLO; bench uses
`RedCarCropper` crop-then-detect because toy tires are ~5-10 px; `"crop": null` in config for
full scale) -> bottom-center of `tire_front_driver` box -> `GroundPlaneCalibrator` (homography,
inches) -> `PositionKalmanFilter` x2 -> minus `alignment` target (set with **z** key) ->
`GuidanceStateMachine` -> `OutputHub` (avatar HTTP POST, Arduino serial, console).

Signal strings (stable contract): MOVE_LEFT, MOVE_RIGHT, STRAIGHT, STOP, CONVEYOR_MOVING, WAIT.
Display text says "TURN WHEEL LEFT/RIGHT".

## Invariants - keep these
- **Fail-safe:** lost/ambiguous detection -> WAIT, never a "go" signal. Tests check it.
- Avatar server and Arduino sketch drop to WAIT if no heartbeat for 2 s; pipeline re-sends every 0.5 s.
- A dead output never crashes the loop.
- Coordinates: x=0 track centerline, **+x = driver's right** facing into the tunnel; y = inches
  before the stop line (+ toward the approaching car).
- The screen faces the driver: driver's left = screen left. Miles faces the driver, so his
  RIGHT arm points to the screen's LEFT.
- Never use horizontal-flip augmentation when training (swaps driver/passenger side).
- After STOP/conveyor, a car seen > `rearm_distance_in` back re-arms guiding; lost for
  `departure_frames` -> IDLE + Kalman reset.

## Bench facts
- Camera index is in `config/bench.json` `"source"` (1 on Fred's laptop; Surface has front + IR cams too).
  Windows needs `cv2.CAP_DSHOW`.
- Bench tolerances: lateral 0.5 in, stop zone 1 in, rearm 3 in, departure 10 frames.
- Red floor at the bench confused the red-car crop -> `search_area` polygon (`set_search_area.py`).
- Only the red toy car is detectable on the bench (color crop + model trained on it).
- Laptop has no NVIDIA GPU (CPU inference ~80 ms/frame). Training was done on an RTX 4090 PC.

## Model / data
- `roboflow/tire_model.pt`: YOLOv8n, 2 classes `tire_front_driver`, `tire_rear_driver`, trained on
  28 hand-labeled 640px crops (`roboflow/seed/`). Toy only.
- Roboflow: workspace `curtis-herbsleb-gocarwash-com`, project `object-detection-thctg`.
  Classes renamed 2026-10-07 (`0`->tire_front_driver, `1`->tire_rear_driver). 157 crops still
  unassigned; old `object-detection` class (71 boxes) unexplained. Big datasets are gitignored.

## Miles avatar
- `avatar_display.html` + `avatar_server.py` (serves `/status`, `/update`, `/assets/*` from
  `avatar_assets/` only). three.js r160 is vendored in `avatar_assets/vendor` (works offline).
- `miles_textured.glb` = Meshy textured A-pose model (no skeleton). Shoulder/elbow bones are
  added in JS from `miles_rig.json`; arm poses are direction vectors in `armPose()`.
  `miles_rig.glb` = vertex-painted fallback. Brand colors: orange #FF6A00, cyan #00B5EC.
- `avatar_display_simple.html` = old 2D fallback page.

## Running
`setup.bat` (once), `start_avatar.bat`, `start_guidance.bat`, `run_tool.bat <script>`.
Tests: `run_tool.bat -m pytest tests` (hardware-free).

## Open items
- 157 unassigned Roboflow crops; label review; no Roboflow version with crops.
- Wheel-angle estimate (front vs rear tire) not built yet - lateral position only.
- Dual-camera script untested with real cameras.
- Outputs to a real PLC/relay intentionally not built (safety review first).
