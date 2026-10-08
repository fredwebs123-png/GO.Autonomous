"""
GO Autonomous - single-camera guidance pipeline
================================================

camera frame
  -> WheelDetector (YOLO; on the bench: crop around the toy car first)
  -> bottom-center of the driver-side FRONT tire box = ground contact pixel
  -> GroundPlaneCalibrator (pixels -> inches)
  -> PositionKalmanFilter x2 (lateral, longitudinal)
  -> GuidanceStateMachine (debounced STOP, fail-safe WAIT, resets when car leaves)
  -> outputs: avatar page / Arduino sign / console (same signal strings)

Usage (PowerShell, from the project folder):
  python run_guidance.py                              # live camera, config/bench.json
  python run_guidance.py --source 1                   # another camera index
  python run_guidance.py --source my_video.mp4        # recorded video
  python run_guidance.py --source roboflow\\export_v2\\train\\images --resize 640x480
  python run_guidance.py --config config/site_x.json --no-display

Keys in the video window: q = quit, space = pause, e = engage conveyor (manual),
  z = "zero here": park the car exactly where it should stop, press z, and that
      tire position becomes the target (saved to the config file).
"""

import argparse
import json
import time
from pathlib import Path

import cv2

from carwash.calibration import GroundPlaneCalibrator
from carwash.detection import RedCarCropper, WheelDetector, best_of_class
from carwash.guidance import GuidanceState, GuidanceStateMachine
from carwash.outputs import build_outputs
from carwash.overlay import draw_overlay
from carwash.tracking import PositionKalmanFilter

ROOT = Path(__file__).parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


class FrameSource:
    """Camera index, video file, or a folder of images - all read the same way."""

    def __init__(self, source, resize=None, folder_fps=10.0):
        self.resize = resize
        self.images = None
        self.cap = None
        self.folder_dt = 1.0 / folder_fps
        if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
            # CAP_DSHOW avoids the MSMF "can't grab frame" error on Windows.
            self.cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
        elif Path(source).is_dir():
            self.images = sorted(p for p in Path(source).iterdir() if p.suffix.lower() in IMAGE_EXTS)
            self.index = 0
        else:
            self.cap = cv2.VideoCapture(str(source))
        if self.cap is not None and not self.cap.isOpened():
            raise SystemExit(f"Could not open video source {source!r}")
        if self.images is not None and not self.images:
            raise SystemExit(f"No images in {source}")

    def read(self):
        if self.images is not None:
            if self.index >= len(self.images):
                return None
            frame = cv2.imread(str(self.images[self.index]))
            self.index += 1
        else:
            ok, frame = self.cap.read()
            if not ok:
                return None
        if self.resize:
            frame = cv2.resize(frame, self.resize, interpolation=cv2.INTER_AREA)
        return frame

    def release(self):
        if self.cap is not None:
            self.cap.release()


def load_config(path):
    return json.loads(Path(path).read_text())


def build_detector(mcfg):
    crop_cfg = mcfg.get("crop")
    cropper = None
    if crop_cfg and crop_cfg.get("type") == "red_car":
        cropper = RedCarCropper(pad=crop_cfg.get("pad", 0.35), search_area=crop_cfg.get("search_area"))
    return WheelDetector(str(ROOT / mcfg["path"]), conf_threshold=mcfg.get("conf", 0.5),
                         imgsz=mcfg.get("imgsz", 640), cropper=cropper, device=mcfg.get("device"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/bench.json")
    ap.add_argument("--source", default=None, help="camera index, video file, or image folder (overrides config)")
    ap.add_argument("--resize", default=None, help="WxH, e.g. 640x480 (undoes Roboflow's 640x640 stretch)")
    ap.add_argument("--no-display", action="store_true")
    ap.add_argument("--max-frames", type=int, default=0, help="stop after N frames (0 = run forever)")
    args = ap.parse_args()

    cfg = load_config(ROOT / args.config)
    # Where the tracked tire should be when the car is perfectly placed. The tire
    # is not the middle of the car, so this is usually not 0,0. Set it with the z key.
    target = cfg.setdefault("alignment", {"lateral_in": 0.0, "longitudinal_in": 0.0})
    raw_lat = raw_long = None
    source = args.source if args.source is not None else cfg["camera"]["source"]
    resize = args.resize or cfg["camera"].get("resize")
    if isinstance(resize, str):
        resize = tuple(int(v) for v in resize.lower().split("x"))
    display = cfg.get("display", True) and not args.no_display

    calib = GroundPlaneCalibrator.from_json(ROOT / cfg["calibration_file"])
    if calib.placeholder:
        print("WARNING: calibration is a PLACEHOLDER - inches are meaningless. Run calibrate.py.")

    mcfg = cfg["model"]
    detector = build_detector(mcfg)
    front_class = mcfg.get("front_class", "tire_front_driver")

    tcfg = cfg.get("tracking", {})
    lateral_kf = PositionKalmanFilter(**tcfg)
    longitudinal_kf = PositionKalmanFilter(**tcfg)
    fsm = GuidanceStateMachine(**cfg.get("guidance", {}))
    outputs = build_outputs(cfg.get("outputs", {}))
    conveyor = cfg.get("conveyor", {})

    frames = FrameSource(source, resize)
    last_t = time.monotonic()
    fps = 0.0
    stopped_since = None
    paused = False
    n = 0

    try:
        while True:
            if not paused:
                frame = frames.read()
                if frame is None:
                    print("End of source.")
                    break
                n += 1
                now = time.monotonic()
                dt = now - last_t
                last_t = now
                if frames.images is not None:
                    dt = frames.folder_dt
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if dt > 0 else fps

                detections = detector.infer(frame)
                front = best_of_class(detections, front_class)
                contact = None
                if front is not None:
                    contact = front.ground_contact_pixel()
                    wx, wy = calib.pixel_to_world(*contact)
                    lateral_kf.predict(dt)
                    lateral_kf.update(wx)
                    longitudinal_kf.predict(dt)
                    longitudinal_kf.update(wy)
                    raw_lat, raw_long = lateral_kf.position, longitudinal_kf.position
                    lateral = raw_lat - target["lateral_in"]
                    longitudinal = raw_long - target["longitudinal_in"]
                else:
                    lateral, longitudinal = None, None

                state, signal = fsm.update(lateral, longitudinal, front is not None)

                if fsm.just_departed:
                    lateral_kf.reset()
                    longitudinal_kf.reset()
                    stopped_since = None
                    print("Vehicle departed - reset for next car.")

                # Bench stand-in for the PLC: engage after STOP has held for a few seconds.
                if state == GuidanceState.STOPPED:
                    stopped_since = stopped_since or now
                    if conveyor.get("simulate") and now - stopped_since >= conveyor.get("engage_after_stop_s", 3.0):
                        fsm.engage_conveyor()
                        state, signal = fsm.state, "CONVEYOR_MOVING"
                        print("Conveyor engaged (simulated).")
                elif state != GuidanceState.CONVEYOR_ENGAGED:
                    stopped_since = None

            outputs.send(signal)

            if display:
                view = draw_overlay(frame, detections, detector.last_crop_box, contact, state, signal,
                                    lateral, longitudinal, fps, calib.placeholder, calib,
                                    getattr(detector.cropper, "search_area", None))
                cv2.imshow("GO Autonomous - q quit, space pause, e engage", view)
                wait_ms = int(frames.folder_dt * 1000) if frames.images is not None else 1
                key = cv2.waitKey(wait_ms) & 0xFF
                if key == ord("q"):
                    break
                if key == ord(" "):
                    paused = not paused
                if key == ord("z"):
                    if front is None or raw_lat is None:
                        print("Zero: no tire detected right now - park the car so its box shows, then press z.")
                    else:
                        target["lateral_in"], target["longitudinal_in"] = round(raw_lat, 2), round(raw_long, 2)
                        cfg["alignment"] = target
                        (ROOT / args.config).write_text(json.dumps(cfg, indent=2))
                        print(f"Zeroed: target tire position x={raw_lat:+.2f} in, y={raw_long:.2f} in (saved).")
                if key == ord("e") and fsm.engage_conveyor():
                    print("Conveyor engaged (manual).")

            if args.max_frames and n >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        outputs.send("WAIT", now=float("inf"))
        outputs.close()
        frames.release()
        if display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
