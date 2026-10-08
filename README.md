# GO Autonomous

Self Loading Program - 
Camera-guided car wash conveyor positioning. Bench mock-up with a toy car; same code is meant to move to full-scale equipment by swapping the config, calibration and model. Background and history: `HANDOFF.md`, `roboflow/GO_AUTONOMOUS_NOTES.md`.

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

## Setup (once)
Python environment lives outside OneDrive at `C:\Users\fredw\venvs\goauto` (CPU PyTorch, ultralytics, OpenCV, pyserial).

```powershell
python -m venv C:\Users\fredw\venvs\goauto
C:\Users\fredw\venvs\goauto\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
C:\Users\fredw\venvs\goauto\Scripts\python.exe -m pip install -r requirements.txt
```

## Run (PowerShell, from this folder)
```powershell
$py = "C:\Users\fredw\venvs\goauto\Scripts\python.exe"
& $py avatar_server.py                 # window 1, then open http://localhost:8000
& $py run_guidance.py                  # window 2, live camera 0
& $py run_guidance.py --source video.mp4
& $py calibrate.py                     # replace the placeholder calibration
& $py -m pytest tests
```

## Signals
`MOVE_LEFT` (shown as TURN WHEEL LEFT), `MOVE_RIGHT` (TURN WHEEL RIGHT), `STRAIGHT`, `STOP`, `CONVEYOR_MOVING`, `WAIT`.
Fail-safe: no/lost detection -> `WAIT`. The avatar and the Arduino also fall back to `WAIT` if the pipeline stops sending for 2 s.
World coordinates: x = 0 on the track centerline, +x = driver's right facing into the tunnel; y = inches before the stop line.
