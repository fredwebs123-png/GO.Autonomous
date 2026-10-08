"""
Shows one snapshot from every camera index so you can pick the right one.
Close run_guidance.py / camera apps first - a camera in use won't show up.

Usage:  python find_cameras.py
Then put the number of the right camera in config/bench.json -> "camera": {"source": N}
"""

import cv2
import numpy as np

tiles = []
for i in range(6):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    ok, frame = False, None
    if cap.isOpened():
        for _ in range(15):  # let exposure settle; IR cameras often show black
            ok, frame = cap.read()
    cap.release()
    if not ok:
        print(f"camera {i}: nothing")
        continue
    h, w = frame.shape[:2]
    print(f"camera {i}: {w}x{h}")
    tile = cv2.resize(frame, (400, 300))
    cv2.putText(tile, f"source {i}", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5)
    cv2.putText(tile, f"source {i}", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    tiles.append(tile)

if tiles:
    cv2.imshow("Cameras - press any key to close", np.hstack(tiles))
    cv2.waitKey(0)
    cv2.destroyAllWindows()
else:
    print("No cameras found. Is the USB camera plugged in and not used by another app?")
