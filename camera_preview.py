"""
Standalone camera preview - shows the live webcam feed in a window so you can
check framing, positioning, and plan your calibration reference points.

Press 'q' in the video window to quit.
"""

import cv2

CAMERA_INDEX = 0  # change to 1, 2, etc. if this doesn't open the right camera

print("Opening camera...")
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW per your earlier fix on Windows

if not cap.isOpened():
    print("Could not open camera. Try changing CAMERA_INDEX to 1 or 2.")
else:
    print("Camera opened. Press 'q' in the video window to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        cv2.imshow("Camera Preview - press 'q' to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed.")
