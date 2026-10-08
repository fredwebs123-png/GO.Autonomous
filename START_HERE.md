# GO Autonomous - start instructions

Two PowerShell windows: **A** = Miles screen, **B** = camera program.

## Every time

**Window A (Miles screen)**
```
cd "C:\Users\fredw\OneDrive\Desktop\GO Autonomous"
C:\Users\fredw\venvs\goauto\Scripts\python.exe avatar_server.py
```
Open Chrome at http://localhost:8000, then press F11 for full screen.

**Window B (camera program)**
```
cd "C:\Users\fredw\OneDrive\Desktop\GO Autonomous"
C:\Users\fredw\venvs\goauto\Scripts\python.exe run_guidance.py
```
Wait about 10 s for the video window. Keys (click the video window first): q quit, space pause, e engage conveyor.

**Shut down:** press q in the video window, then Ctrl+C in Window A.

## Only when something changes
| Situation | Run (in the project folder) |
|---|---|
| Check Miles without the camera | `C:\Users\fredw\venvs\goauto\Scripts\python.exe avatar_server.py --demo` |
| Wrong camera | `...python.exe find_cameras.py`, then put the number in `config\bench.json` under `"source"` (currently 1) |
| Camera or mat moved | `...python.exe set_search_area.py`, then `...python.exe calibrate.py --source 1`, then zero (next row) |
| Says TURN when the car is placed right | Park the car exactly where it should stop, click the video window, press **z** |
| Arduino sign | Upload `carwash_led_sign.ino`, close Serial Monitor, set `"arduino": {"enabled": true` in `config\bench.json` |

## Quick fixes
| Problem | Fix |
|---|---|
| `can't open file ... system32` | You forgot the `cd` line |
| localhost won't load | Window A isn't running |
| "Port 8000 is already in use" | Another avatar server is open; close that window |
| Miles stuck on "Waiting..." | Window B isn't running or doesn't see a tire |
| "UNCALIBRATED" in video | Run `calibrate.py` |
| `Access is denied` on COM6 | Close the Arduino Serial Monitor |
