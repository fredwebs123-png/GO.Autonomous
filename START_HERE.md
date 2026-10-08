# GO Autonomous - start instructions

## New PC (once)
1. Install **Git for Windows** (git-scm.com) and **Python 3.11+** (python.org - tick "Add python.exe to PATH").
2. Open PowerShell and run:
   ```
   git clone https://github.com/fredwebs123-png/GO.Autonomous.git C:\code\go-autonomous
   ```
   Sign in to GitHub when asked. The repo is private, so that GitHub account needs access
   (owner adds it: GitHub > repo > Settings > Collaborators > Add people).
3. In File Explorer, open `C:\code\go-autonomous` and double-click **setup.bat**.
   Takes about 5-10 minutes and ends with "N passed" from the tests.
4. Pick the camera: plug in the USB camera, then in PowerShell in the project folder run
   `.\run_tool.bat find_cameras.py` and put the right number in `config\bench.json` under `"source"`.
5. Calibrate for that camera and mat (see "Only when something changes" below).

## Every time
Double-click in the project folder:
1. **start_avatar.bat** - then open Chrome at http://localhost:8000 and press F11.
2. **start_guidance.bat** - wait about 10 s for the video window.
   Keys (click the video window first): q quit, space pause, e engage conveyor, z zero here.

Shut down: q in the video window, then close the avatar window.

## Syncing between PCs
In PowerShell, in the project folder:
- Before you start: `git pull`
- When you're done: `git add -A`, then `git commit -m "what you changed"`, then `git push`

Calibration and camera settings live in `config\` and travel with git. If two PCs use
different cameras or mats, recalibrate on each and commit settings only from the main bench PC.

## Only when something changes
Run these in PowerShell from the project folder.

| Situation | Run |
|---|---|
| Check Miles without the camera | `.\start_avatar.bat --demo` |
| Wrong camera | `.\run_tool.bat find_cameras.py`, then set `"source"` in `config\bench.json` |
| Camera or mat moved | `.\run_tool.bat set_search_area.py`, then `.\run_tool.bat calibrate.py --source 1`, then zero (next row) |
| Says TURN when the car is placed right | Park the car exactly where it should stop, click the video window, press **z** |
| Arduino sign | Upload `carwash_led_sign.ino`, close Serial Monitor, set `"arduino": {"enabled": true` in `config\bench.json` |
| Run the tests | `.\run_tool.bat -m pytest tests` |

## Quick fixes
| Problem | Fix |
|---|---|
| "Python environment not found" | Run setup.bat |
| localhost won't load | start_avatar.bat isn't running |
| "Port 8000 is already in use" | Another avatar server is open; close that window |
| Miles stuck on "Waiting..." | start_guidance.bat isn't running or doesn't see a tire (bench: only the red toy car works) |
| "UNCALIBRATED" in video | Run calibrate.py |
| `Access is denied` on COM6 | Close the Arduino Serial Monitor |
