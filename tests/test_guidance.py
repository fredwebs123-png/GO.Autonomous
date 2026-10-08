"""State machine, tracking and output tests. No camera, model or hardware needed.

Run:  python -m pytest tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carwash.guidance import (  # noqa: E402
    CONVEYOR_MOVING, MOVE_LEFT, MOVE_RIGHT, STOP, STRAIGHT, WAIT,
    GuidanceState, GuidanceStateMachine,
)
from carwash.outputs import OutputHub  # noqa: E402
from carwash.tracking import PositionKalmanFilter  # noqa: E402


def fsm(**kw):
    defaults = dict(lateral_tolerance_in=3.0, stop_zone_in=6.0, required_consecutive_frames=5, departure_frames=10)
    defaults.update(kw)
    return GuidanceStateMachine(**defaults)


def aligned(m, n):
    for _ in range(n):
        out = m.update(0.0, 2.0, True)
    return out


# --- direction ---------------------------------------------------------------

def test_too_far_right_turns_wheel_left():
    assert fsm().update(5.0, 50.0, True)[1] == MOVE_LEFT


def test_too_far_left_turns_wheel_right():
    assert fsm().update(-5.0, 50.0, True)[1] == MOVE_RIGHT


def test_centered_is_straight():
    assert fsm().update(1.0, 50.0, True)[1] == STRAIGHT


def test_tolerance_edge_counts_as_centered():
    m = fsm()
    assert m.update(3.0, 50.0, True)[1] == STRAIGHT
    assert m.update(-3.0, 50.0, True)[1] == STRAIGHT
    assert m.update(3.01, 50.0, True)[1] == MOVE_LEFT


# --- fail-safe ---------------------------------------------------------------

def test_no_detection_from_idle_is_wait():
    state, signal = fsm().update(None, None, False)
    assert (state, signal) == (GuidanceState.IDLE, WAIT)


def test_lost_detection_while_guiding_is_wait():
    m = fsm()
    m.update(0.0, 50.0, True)
    assert m.update(None, None, False)[1] == WAIT


def test_invalid_flag_wins_even_with_numbers():
    m = fsm()
    m.update(0.0, 50.0, True)
    assert m.update(0.0, 2.0, False)[1] == WAIT


def test_lost_frame_cancels_stop():
    m = fsm()
    assert aligned(m, 5)[1] == STOP
    assert m.update(None, None, False)[1] == WAIT
    # must re-earn STOP with a full streak
    assert aligned(m, 4)[1] == STRAIGHT
    assert aligned(m, 1)[1] == STOP


# --- debounce ----------------------------------------------------------------

def test_stop_needs_n_consecutive_frames():
    m = fsm()
    for _ in range(4):
        assert m.update(0.0, 2.0, True)[1] == STRAIGHT
    assert m.update(0.0, 2.0, True)[1] == STOP


def test_misaligned_frame_resets_streak():
    m = fsm()
    aligned(m, 4)
    m.update(5.0, 2.0, True)
    assert aligned(m, 4)[1] != STOP
    assert aligned(m, 1)[1] == STOP


def test_centered_but_far_does_not_stop():
    m = fsm()
    for _ in range(20):
        assert m.update(0.0, 30.0, True)[1] == STRAIGHT


# --- conveyor and departure ---------------------------------------------------

def test_engage_only_from_stopped():
    m = fsm()
    m.update(0.0, 50.0, True)
    assert not m.engage_conveyor()
    aligned(m, 5)
    assert m.engage_conveyor()
    assert m.update(0.0, 2.0, True)[1] == CONVEYOR_MOVING


def test_conveyor_keeps_moving_when_vehicle_leaves_view_then_resets():
    m = fsm(departure_frames=3)
    aligned(m, 5)
    m.engage_conveyor()
    assert m.update(None, None, False)[1] == CONVEYOR_MOVING
    assert m.update(None, None, False)[1] == CONVEYOR_MOVING
    state, signal = m.update(None, None, False)
    assert (state, signal) == (GuidanceState.IDLE, WAIT)
    assert m.just_departed


def test_next_vehicle_is_guided_after_departure():
    m = fsm(departure_frames=2)
    aligned(m, 5)
    m.update(None, None, False)
    m.update(None, None, False)
    assert m.state == GuidanceState.IDLE
    assert m.update(6.0, 80.0, True)[1] == MOVE_LEFT


def test_departure_flag_is_one_shot():
    m = fsm(departure_frames=1)
    m.update(0.0, 50.0, True)
    m.update(None, None, False)
    assert m.just_departed
    m.update(None, None, False)
    assert not m.just_departed


# --- tracking ------------------------------------------------------------------

def test_kalman_converges_and_resets():
    kf = PositionKalmanFilter(dt=1 / 30)
    for _ in range(60):
        kf.predict()
        kf.update(10.0)
    assert abs(kf.position - 10.0) < 0.5
    kf.reset()
    assert not kf.initialized
    kf.update(-4.0)
    assert kf.position == -4.0


def test_kalman_tracks_velocity():
    kf = PositionKalmanFilter(dt=0.1, process_noise=10.0)
    for i in range(100):
        kf.predict(0.1)
        kf.update(100.0 - 2.0 * i * 0.1)  # approaching at 2 in/s
    assert abs(kf.velocity + 2.0) < 0.3


# --- outputs -------------------------------------------------------------------

class Recorder:
    def __init__(self, name="avatar", fail=False):
        self.name, self.fail, self.sent = name, fail, []

    def send(self, signal):
        if self.fail:
            raise OSError("server down")
        self.sent.append(signal)

    def close(self):
        pass


def test_hub_sends_changes_and_heartbeat():
    r = Recorder()
    hub = OutputHub([r], resend_interval_s=0.5)
    hub.send(STRAIGHT, now=0.0)
    hub.send(STRAIGHT, now=0.1)   # suppressed
    hub.send(MOVE_LEFT, now=0.2)  # change -> sent
    hub.send(MOVE_LEFT, now=0.8)  # heartbeat -> sent
    assert r.sent == [STRAIGHT, MOVE_LEFT, MOVE_LEFT]


def test_dead_output_never_crashes_loop():
    good, bad = Recorder(), Recorder("arduino", fail=True)
    hub = OutputHub([bad, good])
    hub.send(STOP, now=0.0)
    hub.send(WAIT, now=1.0)
    assert good.sent == [STOP, WAIT]


def test_rearms_when_car_backs_up_after_conveyor():
    m = fsm(rearm_distance_in=18.0)
    aligned(m, 5)
    m.engage_conveyor()
    assert m.update(0.0, 10.0, True)[1] == CONVEYOR_MOVING   # inside rearm distance: keep going
    state, signal = m.update(5.0, 30.0, True)                # well back up the lane
    assert state == GuidanceState.GUIDING and signal == MOVE_LEFT


def test_rearms_from_stopped_when_car_backs_up():
    m = fsm()
    aligned(m, 5)
    assert m.update(0.0, 30.0, True)[1] == STRAIGHT


def test_rearm_default_is_three_stop_zones():
    assert fsm(stop_zone_in=2.0).rearm_distance_in == 6.0
