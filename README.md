# GO Autonomous

**Self Loading Program** - camera-guided car wash conveyor positioning. Bench mock-up with a toy car; same code is meant to move to full-scale equipment by swapping the config, calibration and model. Background and history: `HANDOFF.md`, `roboflow/GO_AUTONOMOUS_NOTES.md`.

## Layout
| Path | What |
|---|---|
| `carwash/` | Shared code: calibration, detection (+ bench crop step), tracking, guidance state machine, outputs, debug overlay |
| `run_guidance.py` | Main single-camera pipeline |
| `calibrate.py` | Click ground marks, enter inches, saves `config/calibration_*.json` |
| `config/bench.json` | Bench settings (camera, model, tolerances, outputs). Copy per site |
| `avatar_server.py` + `avatar_display.html` | On-screen driver guidance |
| `carwash_led_sign.ino`, `test_arduino_leds.py` | Arduino LED sign (COM6) |
| `car_wash_guidance_dual_camera.py` | Two-camera variant (untested with real cameras) |
| `tests/` | Hardware-free tests |
| `roboflow/` | Dataset work, crop tool, `tire_model.pt` (toy-car model) |
| `archive/` | Original skeleton, superseded by `carwash/` + `run_guidance.py` |
| `avatar_assets/` | Miles 3D models (`miles_textured.glb` used, `miles_rig.glb` fallback), joint positions, three.js |
| `set_search_area.py`, `find_cameras.py` | Bench setup helpers |
| `*.bat` | Setup and start launchers (no hard-coded paths) |
| `CLAUDE.md` | Project status/context for Claude Code sessions on any PC |

## Setup and running
See **START_HERE.md**. Short version: `setup.bat` once per PC (creates `.venv`,
installs CPU PyTorch + `requirements.txt`, runs tests), then `start_avatar.bat` and
`start_guidance.bat`. `run_tool.bat <script> [args]` runs any script with the project Python.

- `requirements-assets.txt`: extra packages only needed to re-process 3D models (trimesh etc.).
- **GPU (training PC only):** after setup, swap in CUDA PyTorch:
  `.venv\Scripts\python.exe -m pip install --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu128`
  then retrain with `roboflow/train_seed.py`.

## Data that is NOT in git
| What | Where |
|---|---|
| Roboflow dataset (409 toy frames, 409 crops, labels) | Roboflow workspace `curtis-herbsleb-gocarwash-com`, project `object-detection-thctg`; full local copy in the original OneDrive folder `Desktop\GO Autonomous\roboflow` |
| Model predictions / training runs | Same OneDrive folder (re-creatable with `roboflow/train_seed.py`) |
| Raw Meshy downloads (STL, untextured GLB) | Meshy account / OneDrive folder `avatar_assets` |
| Future site video | External drive or cloud storage, not git (too big) |

## Signals
`MOVE_LEFT` (shown as TURN WHEEL LEFT), `MOVE_RIGHT` (TURN WHEEL RIGHT), `STRAIGHT`, `STOP`, `CONVEYOR_MOVING`, `WAIT`.
Fail-safe: no/lost detection -> `WAIT`. The avatar and the Arduino also fall back to `WAIT` if the pipeline stops sending for 2 s.
World coordinates: x = 0 on the track centerline, +x = driver's right facing into the tunnel; y = inches before the stop line.
