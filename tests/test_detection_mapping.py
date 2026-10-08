"""Crop/box mapping and calibration tests (needs numpy + opencv, no model)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carwash.detection import Detection, RedCarCropper, best_of_class, map_crop_box_to_frame  # noqa: E402


def test_box_maps_back_from_crop_to_frame():
    # 200x200 crop at (100, 50), resized to 640
    crop_box = (100, 50, 300, 250)
    assert map_crop_box_to_frame((0, 0, 640, 640), crop_box, 640) == (100, 50, 300, 250)
    x1, y1, x2, y2 = map_crop_box_to_frame((320, 320, 640, 640), crop_box, 640)
    assert (x1, y1, x2, y2) == (200, 150, 300, 250)


def test_ground_contact_is_bottom_center():
    assert Detection(10, 20, 30, 60, 0.9, "tire_front_driver").ground_contact_pixel() == (20, 60)


def test_best_of_class():
    dets = [Detection(0, 0, 1, 1, 0.6, "tire_front_driver"),
            Detection(0, 0, 1, 1, 0.9, "tire_front_driver"),
            Detection(0, 0, 1, 1, 0.99, "tire_rear_driver")]
    assert best_of_class(dets, "tire_front_driver").confidence == 0.9
    assert best_of_class(dets, "nope") is None


def test_red_cropper_finds_red_blob_and_ignores_gray():
    frame = np.full((480, 640, 3), 128, np.uint8)  # BGR gray
    assert RedCarCropper().find_crop(frame) is None
    frame[200:260, 300:400] = (30, 30, 220)  # red in BGR
    x0, y0, x1, y1 = RedCarCropper().find_crop(frame)
    assert x0 <= 300 and y0 <= 200 and x1 >= 400 and y1 >= 260
    assert x1 - x0 == y1 - y0  # square


def test_calibration_round_trip(tmp_path):
    cv2 = pytest.importorskip("cv2")  # noqa: F841
    from carwash.calibration import GroundPlaneCalibrator

    img = [(100, 100), (500, 100), (100, 400), (500, 400)]
    world = [(-20, 100), (20, 100), (-20, 0), (20, 0)]
    c = GroundPlaneCalibrator(img, world)
    assert max(c.reprojection_errors()) < 1e-6
    x, y = c.pixel_to_world(300, 250)
    assert abs(x) < 1e-6 and abs(y - 50) < 1e-6
    c.to_json(tmp_path / "c.json")
    c2 = GroundPlaneCalibrator.from_json(tmp_path / "c.json")
    assert c2.pixel_to_world(300, 250) == pytest.approx((x, y))


def test_search_area_ignores_red_outside_mat():
    pytest.importorskip("cv2")
    frame = np.full((480, 640, 3), 128, np.uint8)
    frame[0:120, :] = (30, 30, 200)          # big red "floor" strip at the top
    frame[300:340, 300:380] = (30, 30, 220)  # small red car on the mat
    mat = [[100, 200], [600, 200], [600, 470], [100, 470]]
    x0, y0, x1, y1 = RedCarCropper().find_crop(frame)
    assert y0 < 120  # without a search area the floor wins
    x0, y0, x1, y1 = RedCarCropper(search_area=mat).find_crop(frame)
    assert x0 <= 300 and x1 >= 380 and y0 <= 300 and y1 >= 340 and y0 > 120
