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
