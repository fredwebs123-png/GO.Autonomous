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
