"""
Calibration helper - maps camera pixels to inches on the ground.

Setup: put 4-8 tape marks on the ground the camera can see, spread across
the whole approach area (not in a line). Measure each one in inches:
    x = sideways from the track centerline, + = DRIVER'S RIGHT facing into the tunnel
    y = distance before the stop line, + = toward the approaching car (0 = stop line)

Usage (PowerShell, from the project folder):
  python calibrate.py                              # live camera 0
  python calibrate.py --source 1
  python calibrate.py --image calib_photo.jpg      # a saved frame
  python calibrate.py --out config/calibration_site_x.json

In the window:
  left-click  add a point, then type its "x,y" inches in this terminal
  u           undo last point
  t           test mode: click anywhere to see its computed inches (check a mark you did NOT use)
  s           save (needs 4+ points) - prints the error at each point
  q           quit
"""

import argparse
from pathlib import Path

import cv2

from carwash.calibration import GroundPlaneCalibrator

ROOT = Path(__file__).parent
WIN = "Calibration - click points, s save, t test, u undo, q quit"


def grab_frame(args):
    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            raise SystemExit(f"Could not read {args.image}")
        return frame
    cap = cv2.VideoCapture(int(args.source), cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {args.source}")
    print("Live view: press SPACE to freeze the frame you want to calibrate on.")
    frame = None
    while True:
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("Failed to grab frame")
        cv2.imshow(WIN, frame)
        if cv2.waitKey(1) & 0xFF == ord(" "):
            break
    cap.release()
    return frame


def ask_inches(px, py):
    while True:
        raw = input(f"Pixel ({px}, {py}) -> enter x,y inches (blank = cancel): ").strip()
        if not raw:
            return None
        try:
            x, y = (float(v) for v in raw.replace(" ", "").split(","))
            return x, y
        except ValueError:
            print("  Format is x,y  e.g.  -24,120")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0")
    ap.add_argument("--image", default=None)
    ap.add_argument("--out", default="config/calibration_bench.json")
    args = ap.parse_args()

    frame = grab_frame(args)
    if args.image is None:
        snap = ROOT / "config" / "calibration_frame.jpg"
        cv2.imwrite(str(snap), frame)
        print(f"Saved the frozen frame to {snap} (re-run with --image to redo).")

    img_pts, world_pts = [], []
    state = {"test": False, "calib": None, "probe": None}

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if state["test"] and state["calib"] is not None:
            state["probe"] = (x, y, *state["calib"].pixel_to_world(x, y))
            print(f"  test point ({x},{y}) -> x={state['probe'][2]:+.1f} in, y={state['probe'][3]:.1f} in")
            return
        w = ask_inches(x, y)
        if w is not None:
            img_pts.append((x, y))
            world_pts.append(w)

    cv2.namedWindow(WIN)
    cv2.setMouseCallback(WIN, on_click)
    while True:
        view = frame.copy()
        for (px, py), (wx, wy) in zip(img_pts, world_pts):
            cv2.circle(view, (px, py), 5, (0, 0, 255), -1)
            cv2.putText(view, f"({wx:g},{wy:g})", (px + 6, py - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        if state["probe"]:
            px, py, wx, wy = state["probe"]
            cv2.drawMarker(view, (px, py), (0, 255, 0), cv2.MARKER_CROSS, 14, 2)
            cv2.putText(view, f"{wx:+.1f},{wy:.1f}", (px + 6, py + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        mode = "TEST MODE" if state["test"] else f"{len(img_pts)} points"
        cv2.putText(view, mode, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(WIN, view)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            break
        if key == ord("u") and img_pts:
            img_pts.pop()
            world_pts.pop()
        if key in (ord("s"), ord("t")):
            if len(img_pts) < 4:
                print("Need at least 4 points first.")
                continue
            try:
                calib = GroundPlaneCalibrator(img_pts, world_pts)
            except ValueError as e:
                print(f"Calibration failed: {e}")
                continue
            state["calib"] = calib
            if key == ord("t"):
                state["test"] = not state["test"]
                print("Test mode", "ON - click a mark you did not use" if state["test"] else "OFF")
                continue
            errs = calib.reprojection_errors()
            for (wx, wy), e in zip(world_pts, errs):
                print(f"  point ({wx:g},{wy:g}) error {e:.2f} in")
            print(f"  worst error {max(errs):.2f} in" + ("  <- re-check that mark" if max(errs) > 1.0 else ""))
            if len(img_pts) == 4:
                print("  (With exactly 4 points the error is always 0 - press t and click a spare mark to really check.)")
            if any(py < 5 or px < 5 for px, py in img_pts):
                print("  WARNING: a point is at the very edge of the picture - probably a mis-click. Press u and redo it.")
            calib.to_json(ROOT / args.out)
            print(f"Saved {args.out}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
