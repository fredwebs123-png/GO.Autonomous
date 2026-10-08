"""
Set the area where the program looks for the toy car (bench mock-up only).

Click the corners of the white mat. Red outside that outline (a red floor,
wall, furniture) is then ignored, so it can't be mistaken for the car.
Re-run this whenever the camera or mat moves.

Usage (PowerShell, from the project folder):
  python set_search_area.py                 # uses the camera in config/bench.json
  python set_search_area.py --source 1

In the window:
  SPACE   freeze the live picture (the car can be anywhere, it doesn't matter)
  click   add a corner (go around the mat in order, 3+ corners)
  u       undo last corner
  c       clear and use the whole picture again
  s       save to the config file
  q       quit without saving
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).parent
WIN = "Search area - SPACE freeze, click corners, s save, u undo, q quit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/bench.json")
    ap.add_argument("--source", default=None)
    args = ap.parse_args()

    cfg_path = ROOT / args.config
    cfg = json.loads(cfg_path.read_text())
    source = int(args.source if args.source is not None else cfg["camera"]["source"])

    cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {source}. Close run_guidance.py and other camera apps first.")
    frame = None
    while True:
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("Failed to grab frame")
        view = frame.copy()
        cv2.putText(view, "SPACE to freeze", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow(WIN, view)
        if cv2.waitKey(1) & 0xFF == ord(" "):
            break
    cap.release()

    pts = [list(p) for p in (cfg["model"].get("crop") or {}).get("search_area") or []]

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append([x, y])

    cv2.setMouseCallback(WIN, on_click)
    while True:
        view = frame.copy()
        if len(pts) >= 3:
            shade = view.copy()
            outside = np.ones(view.shape[:2], np.uint8)
            cv2.fillPoly(outside, [np.array(pts, np.int32)], 0)
            shade[outside.astype(bool)] = (shade[outside.astype(bool)] * 0.35).astype(np.uint8)
            view = shade
        for i, (x, y) in enumerate(pts):
            cv2.circle(view, (x, y), 5, (0, 200, 255), -1)
            if i:
                cv2.line(view, tuple(pts[i - 1]), (x, y), (0, 200, 255), 2)
        if len(pts) >= 3:
            cv2.line(view, tuple(pts[-1]), tuple(pts[0]), (0, 200, 255), 2)
        msg = f"{len(pts)} corners - click mat corners, s save" if pts else "click the corners of the mat"
        cv2.putText(view, msg, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(WIN, view)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            print("Quit without saving.")
            break
        if key == ord("u") and pts:
            pts.pop()
        if key == ord("c"):
            pts.clear()
        if key == ord("s"):
            if pts and len(pts) < 3:
                print("Need at least 3 corners (or press c to clear and use the whole picture).")
                continue
            crop = cfg["model"].get("crop") or {"type": "red_car", "pad": 0.35}
            crop["search_area"] = pts or None
            cfg["model"]["crop"] = crop
            cfg_path.write_text(json.dumps(cfg, indent=2))
            print(f"Saved {len(pts)} corners to {args.config}" if pts else "Cleared search area (whole picture).")
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
