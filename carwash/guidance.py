"""Guidance state machine: turns a smoothed tire position into a driver signal.

Signal contract (shared by the avatar page, the Arduino sign and any future
output). The strings are kept stable so every output keeps working:

    MOVE_LEFT        tire is right of the track centerline -> driver turns wheel LEFT
    MOVE_RIGHT       tire is left of the centerline        -> driver turns wheel RIGHT
    STRAIGHT         centered, keep the wheel straight and keep rolling
    STOP             aligned and in the stop zone for N consecutive frames
    CONVEYOR_MOVING  conveyor engaged
    WAIT             no valid detection / fail-safe default

Fail-safe rule: a lost or ambiguous detection always produces WAIT, never a
"go" signal. Keep this invariant in all changes (tests/test_guidance.py
checks it).

Coordinates: x = 0 at the track centerline, +x = the DRIVER'S RIGHT when
facing into the tunnel. y = inches remaining to the stop line (shrinks as
the car approaches; negative = past the line). Units: inches.
"""

from enum import Enum, auto

MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
STRAIGHT = "STRAIGHT"
STOP = "STOP"
CONVEYOR_MOVING = "CONVEYOR_MOVING"
WAIT = "WAIT"

ALL_SIGNALS = (MOVE_LEFT, MOVE_RIGHT, STRAIGHT, STOP, CONVEYOR_MOVING, WAIT)


class GuidanceState(Enum):
    IDLE = auto()              # no vehicle
    VEHICLE_DETECTED = auto()  # vehicle seen, but this frame's detection was lost
    GUIDING = auto()           # steering the driver toward the centerline
    STOPPED = auto()           # aligned in the stop zone, waiting for conveyor
    CONVEYOR_ENGAGED = auto()  # conveyor running, vehicle being pulled through


class GuidanceStateMachine:
    def __init__(self, lateral_tolerance_in: float = 3.0, stop_zone_in: float = 6.0,
                 required_consecutive_frames: int = 5, departure_frames: int = 30,
                 rearm_distance_in: float | None = None):
        """
        lateral_tolerance_in: |offset| at or below this counts as centered
        stop_zone_in: longitudinal distance at or below this counts as "at the stop line"
        required_consecutive_frames: aligned frames in a row before STOP (debounce)
        departure_frames: lost frames in a row before the vehicle counts as gone
                          and the machine resets to IDLE for the next car
        rearm_distance_in: after STOP / conveyor, a vehicle seen this far back from
                           the stop line is a new approach (or the car backed up),
                           so guiding starts again. Default: 3 x stop_zone_in.
        """
        self.lateral_tolerance_in = lateral_tolerance_in
        self.stop_zone_in = stop_zone_in
        self.required_consecutive_frames = required_consecutive_frames
        self.departure_frames = departure_frames
        self.rearm_distance_in = rearm_distance_in if rearm_distance_in is not None else 3 * stop_zone_in
        self.reset()

    def reset(self):
        self.state = GuidanceState.IDLE
        self._aligned_streak = 0
        self._lost_streak = 0
        self.just_departed = False  # True only on the update that reset to IDLE

    def update(self, lateral_offset_in, longitudinal_dist_in, detection_valid: bool):
        """Advance one frame. Returns (state, signal)."""
        self.just_departed = False

        if not detection_valid or lateral_offset_in is None or longitudinal_dist_in is None:
            return self._handle_lost()

        self._lost_streak = 0

        if self.state in (GuidanceState.IDLE, GuidanceState.VEHICLE_DETECTED):
            self.state = GuidanceState.GUIDING
        elif (self.state in (GuidanceState.STOPPED, GuidanceState.CONVEYOR_ENGAGED)
              and longitudinal_dist_in > self.rearm_distance_in):
            # Vehicle is well back up the lane: backed up, or the next car. Guide again.
            self.state = GuidanceState.GUIDING
            self._aligned_streak = 0

        if self.state == GuidanceState.GUIDING:
            is_centered = abs(lateral_offset_in) <= self.lateral_tolerance_in
            in_stop_zone = longitudinal_dist_in <= self.stop_zone_in
            if is_centered and in_stop_zone:
                self._aligned_streak += 1
            else:
                self._aligned_streak = 0
            if self._aligned_streak >= self.required_consecutive_frames:
                self.state = GuidanceState.STOPPED

        return self.state, self._signal(lateral_offset_in)

    def engage_conveyor(self) -> bool:
        if self.state == GuidanceState.STOPPED:
            self.state = GuidanceState.CONVEYOR_ENGAGED
            return True
        return False

    def _handle_lost(self):
        self._aligned_streak = 0
        self._lost_streak += 1

        if self.state != GuidanceState.IDLE and self._lost_streak >= self.departure_frames:
            self.state = GuidanceState.IDLE
            self.just_departed = True
            return self.state, WAIT

        if self.state == GuidanceState.CONVEYOR_ENGAGED:
            # Vehicle is on the conveyor; losing sight of it is expected.
            return self.state, CONVEYOR_MOVING
        if self.state in (GuidanceState.GUIDING, GuidanceState.STOPPED):
            # Fail-safe: one dropped frame cancels STOP and must re-earn it.
            self.state = GuidanceState.VEHICLE_DETECTED
        return self.state, WAIT

    def _signal(self, lateral_offset_in):
        if self.state == GuidanceState.STOPPED:
            return STOP
        if self.state == GuidanceState.CONVEYOR_ENGAGED:
            return CONVEYOR_MOVING
        if lateral_offset_in > self.lateral_tolerance_in:
            return MOVE_LEFT
        if lateral_offset_in < -self.lateral_tolerance_in:
            return MOVE_RIGHT
        return STRAIGHT
