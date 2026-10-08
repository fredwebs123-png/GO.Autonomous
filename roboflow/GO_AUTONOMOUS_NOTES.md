# Go Autonomous: tire detection notes

Status as of 2026-09-30. Written after an audit of the Roboflow project. No new annotations were added.

## Goal
A mini PC reads a camera feed, detects the driver-side front and rear tires, and indicates which direction to turn the wheels. Runs as a Python script with a Roboflow-trained model.

## Roboflow project
- Workspace: curtis-herbsleb-gocarwash-com
- Project: object-detection (id `object-detection-thctg`)
- URL: https://app.roboflow.com/curtis-herbsleb-gocarwash-com/object-detection-thctg/browse

## Audit (409 images, not 419)
- 17 images have a `tire_front_driver` box (29 boxes).
- 70 images have an `object-detection` box (71 boxes). Purpose unknown, likely a default or test class.
- 322 images have no boxes.
- Subject is a toy red sports car on a paper mat with a taped line. Frames are named `frame_0000.jpg` onward (video frames).

## Changes made
- Renamed class `Front tire` to `tire_front_driver`.
- Added class `tire_rear_driver`.
- Nothing deleted. `object-detection` untouched. No boxes or tags added.

## Why labeling stopped
- The car is about 50 to 70 px wide in the frame. Tires are about 5 to 10 px. Zoomed views show red body blobs, not clear tire edges.
- Roboflow "Find Objects with AI" (SAM 3) returned 0 objects for `tire_front_driver` on `frame_0004.jpg`.
- In `frame_0004.jpg` the car faces the camera, so rear tires are hidden.
- Guessed boxes would hurt training more than no boxes.

## What would unblock it
1. Move the camera closer, or crop to the car, so tires are at least 30 px wide.
2. Capture about 30 frames each of wheels straight, left and right, from the real camera position.
3. Hand-label 10 to 15 frames (box tool), then train, then use the model to label the rest.
4. Decide the meaning of "driver side" when the camera sees the passenger side, and whether the tag set is `wheel_straight`, `wheel_left`, `wheel_right`, `not_visible`.

## Cropping tool
`crop_car.py` crops each frame around the red car (color detection, Pillow and numpy only) and upscales to a fixed size. Frames with no car found are skipped and logged in `crop_log.csv`. Originals are never modified.

    python crop_car.py INPUT_DIR [OUTPUT_DIR] [--size 640] [--pad 0.35]

Ran on the `export_v2` export: 409 of 409 frames cropped. Use `--unstretch 4:3` for Roboflow exports, which are stretched to 640x640. Do not crop from the old `v1` export: it is stretched and likely augmented (flips swap driver and passenger sides). `sample_crop.jpg` and `contact_sheet.jpg` show results.

## Seed labels (done 2026-09-30)
- Source: `export_v2` (Roboflow version 2 export, 409 unique frames, stretched 640x640), cropped with `crop_car.py --unstretch 4:3` into `cropped/` (409 of 409 found a car).
- `seed/` holds 28 labeled crops in YOLO format (`images/`, `labels/`, `data.yaml`, `overlay/` with boxes drawn). Classes: 0 `tire_front_driver`, 1 `tire_rear_driver`. Driver side means the car's left side.
- 21 front and 28 rear driver-side boxes. Boxes were estimated visually from gridded crops and checked on overlays, so expect a few pixels of error. A few (for example frames 0106, 0278, 0315) are lower confidence.
- Most frames (for example 0072, 0174, 0210, 0349, 0383) face the camera head-on, and the driver-side tires are not distinguishable. These were left unlabeled on purpose.
- Small set, but the labeled frames are the angled ones where tires are visible, so a small YOLO model (YOLOv8n) can be trained as a first test. `add_labels.py` writes labels and overlays for more hand-estimated boxes.

## First model (2026-09-30)
- Trained YOLOv8n on the 28 seed crops (no flips, 80/20 split) with `train_seed.py`. Weights: `tire_model.pt` (6 MB).
- Held-out check (5 images, 9 boxes): precision 0.83, recall 0.76, mAP50 0.84, mAP50-95 0.32. Tiny validation set, so treat these as rough.
- Ran over all 409 crops at confidence 0.25: front tire found in 160, rear tire in 224. At confidence 0.5 or more: front 118, rear 137, both 71. Results in `predictions/` (`overlay/`, `labels/` with confidence as last column, `summary.csv`). Sample sheet: `predictions_sheet.jpg`.
- Head-on frames mostly get no detection, as intended. Low-confidence detections (under 0.5) are on less clear frames and need review.
- Training used a temporary venv (PyTorch CUDA + ultralytics, 4.8 GB). It was deleted afterward. To retrain, recreate a venv and run `train_seed.py`. To run the model on the mini PC, install `ultralytics` there and load `tire_model.pt`.

## Planned tags (image level)
`wheel_straight`, `wheel_left`, `wheel_right`, `not_visible`

## Runtime sketch (mini PC)
1. Grab a frame from the camera.
2. Run the Roboflow model (inference package or hosted API) for `tire_front_driver` and `tire_rear_driver`.
3. Compare the front-tire box shape and position to the rear-tire box to estimate wheel angle.
4. Output turn direction: left, right, or straight.
