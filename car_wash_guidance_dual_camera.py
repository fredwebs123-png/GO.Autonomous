"""
Car Wash Vehicle Guidance System - DUAL CAMERA Prototype Skeleton
===================================================================

Extends the single-camera pipeline to run two cameras at different angles,
each with its own calibration and tracking, fused together before being
handed to the guidance state machine. This gets you sensor redundancy
without a break-beam sensor -- if the two cameras disagree or one loses
detection, the system falls back to a conservative "wait" state rather
than trusting a single, possibly-wrong, camera.

Reuses the shared classes in the carwash/ package. Not yet tested with two
real cameras (frame sync and doubled inference load are open questions).
"""

import time
from dataclasses import dataclass

import cv2

from carwash.calibration import GroundPlaneCalibrator
from carwash.detection import WheelDetector, best_of_class
from carwash.guidance import GuidanceStateMachine
from carwash.tracking import PositionKalmanFilter

FRONT_CLASS = "tire_front_driver"


@dataclass
class CameraEstimate:
    lateral_in: float | None
    longitudinal_in: float | None
    confidence: float  # detector confidence, 0.0 if no detection this frame
    valid: bool


class CameraPipeline:
    """
    Wraps one camera's full chain: capture -> detect -> calibrate -> smooth.
    Instantiate one of these per physical camera.
    """

    def __init__(self, camera_source, model_path: str, calibrator, dt: float = 1 / 30.0):
        self.cap_source = camera_source          # e.g. a cv2.VideoCapture index or RTSP URL
        self.detector = WheelDetector(model_path)
        self.calibrator = calibrator              # this camera's own GroundPlaneCalibrator
        self.lateral_kf = PositionKalmanFilter(dt=dt)
        self.longitudinal_kf = PositionKalmanFilter(dt=dt)

    def process_frame(self, frame) -> CameraEstimate:
        best = best_of_class(self.detector.infer(frame), FRONT_CLASS)
        if best is None:
            return CameraEstimate(None, None, confidence=0.0, valid=False)

        px, py = best.ground_contact_pixel()
        world_x, world_y = self.calibrator.pixel_to_world(px, py)

        self.lateral_kf.predict()
        self.lateral_kf.update(world_x)
        self.longitudinal_kf.predict()
        self.longitudinal_kf.update(world_y)

        return CameraEstimate(
            lateral_in=self.lateral_kf.position,
            longitudinal_in=self.longitudinal_kf.position,
            confidence=best.confidence,
            valid=True,
        )


# ---------------------------------------------------------------------------
# FUSION LAYER -- the genuinely new piece vs. the single-camera version
# ---------------------------------------------------------------------------

class DualCameraFusion:
    """
    Reconciles two CameraEstimates into one trusted estimate for the state
    machine. This is where the redundancy benefit actually comes from --
    without this logic, two cameras is just two independent single-camera
    systems bolted together.
    """

    def __init__(self, agreement_tolerance_in: float = 4.0):
        self.agreement_tolerance_in = agreement_tolerance_in

    def fuse(self, est_a: CameraEstimate, est_b: CameraEstimate):
        """
        Returns (lateral_offset, longitudinal_dist, detection_valid) for the
        state machine, exactly matching the single-camera pipeline's contract.
        """
        # Both cameras lost the vehicle -> unambiguous fail-safe
        if not est_a.valid and not est_b.valid:
            return None, None, False

        # Only one camera sees it: usable, but treat as lower-confidence.
        # (Simplest policy: use it. Stricter policy: require both for STOP-zone
        # decisions specifically -- add that check in the state machine caller.)
        if est_a.valid and not est_b.valid:
            return est_a.lateral_in, est_a.longitudinal_in, True
        if est_b.valid and not est_a.valid:
            return est_b.lateral_in, est_b.longitudinal_in, True

        # Both cameras see it -- check agreement
        lateral_diff = abs(est_a.lateral_in - est_b.lateral_in)
        longitudinal_diff = abs(est_a.longitudinal_in - est_b.longitudinal_in)

        if lateral_diff > self.agreement_tolerance_in or longitudinal_diff > self.agreement_tolerance_in:
            # Cameras disagree meaningfully -- something is wrong (occlusion,
            # false detection, miscalibration). Fail safe rather than guess.
            return None, None, False

        # Agreement -- average them, weighted by confidence
        total_conf = est_a.confidence + est_b.confidence
        w_a = est_a.confidence / total_conf
        w_b = est_b.confidence / total_conf

        fused_lateral = est_a.lateral_in * w_a + est_b.lateral_in * w_b
        fused_longitudinal = est_a.longitudinal_in * w_a + est_b.longitudinal_in * w_b

        return fused_lateral, fused_longitudinal, True


# ---------------------------------------------------------------------------
# MAIN LOOP -- dual camera version
# ---------------------------------------------------------------------------

def main():
    # --- one-time setup: each camera gets its OWN calibration, same world coords ---
    calib_a = GroundPlaneCalibrator(
        image_points=[(120, 400), (520, 400), (80, 600), (560, 600)],  # TODO: camera A's measured points
        world_points=[(-24, 120), (24, 120), (-30, 40), (30, 40)],
    )
    calib_b = GroundPlaneCalibrator(
        image_points=[(90, 380), (540, 390), (60, 610), (580, 615)],   # TODO: camera B's measured points
        world_points=[(-24, 120), (24, 120), (-30, 40), (30, 40)],      # SAME real-world targets as camera A
    )

    pipeline_a = CameraPipeline(camera_source=0, model_path="roboflow/tire_model.pt", calibrator=calib_a)
    pipeline_b = CameraPipeline(camera_source=1, model_path="roboflow/tire_model.pt", calibrator=calib_b)

    fusion = DualCameraFusion(agreement_tolerance_in=4.0)
    fsm = GuidanceStateMachine()

    cap_a = cv2.VideoCapture(pipeline_a.cap_source, cv2.CAP_DSHOW)
    cap_b = cv2.VideoCapture(pipeline_b.cap_source, cv2.CAP_DSHOW)

    try:
        while True:
            ret_a, frame_a = cap_a.read()
            ret_b, frame_b = cap_b.read()
            if not ret_a or not ret_b:
                break

            est_a = pipeline_a.process_frame(frame_a)
            est_b = pipeline_b.process_frame(frame_b)

            lateral_offset, longitudinal_dist, detection_valid = fusion.fuse(est_a, est_b)

            state, signal = fsm.update(lateral_offset, longitudinal_dist, detection_valid)

            # TODO: send `signal` to LED sign (see carwash_led_sign.ino)
            # TODO: when state == GuidanceState.STOPPED, call fsm.engage_conveyor()

            print(f"state={state.name:20s} signal={signal:12s} "
                  f"lateral={lateral_offset} longitudinal={longitudinal_dist}")

            time.sleep(1 / 30.0)

    finally:
        cap_a.release()
        cap_b.release()


if __name__ == "__main__":
    main()
