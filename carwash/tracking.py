"""Constant-velocity Kalman filter for one ground axis (inches)."""

import numpy as np


class PositionKalmanFilter:
    """
    Tracks one ground axis (lateral x or longitudinal y). Run one instance
    per axis. State vector: [position, velocity].

    dt can be passed per predict() call so real frame timing is used
    instead of assuming a fixed frame rate.
    """

    def __init__(self, dt: float = 1 / 30.0, process_noise: float = 1.0, measurement_noise: float = 4.0):
        self.dt = dt
        self.q = process_noise
        self.H = np.array([[1.0, 0.0]])
        self.R = np.array([[measurement_noise]])
        self._set_dt(dt)
        self.P = np.eye(2) * 500.0
        self.x = np.zeros((2, 1))
        self.initialized = False

    def _set_dt(self, dt):
        self.dt = dt
        self.F = np.array([[1.0, dt], [0.0, 1.0]])
        self.Q = np.array([[dt**4 / 4, dt**3 / 2], [dt**3 / 2, dt**2]]) * self.q

    def reset(self, initial_position: float | None = None):
        """Forget the current vehicle. With a position, start tracking from it."""
        self.P = np.eye(2) * 500.0
        if initial_position is None:
            self.x = np.zeros((2, 1))
            self.initialized = False
        else:
            self.x = np.array([[float(initial_position)], [0.0]])
            self.initialized = True

    def predict(self, dt: float | None = None):
        if not self.initialized:
            return self.x
        if dt is not None and dt > 0 and dt != self.dt:
            self._set_dt(dt)
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, measurement: float):
        if not self.initialized:
            self.reset(measurement)
            return self.x
        z = np.array([[float(measurement)]])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(2) - K @ self.H) @ self.P
        return self.x

    @property
    def position(self) -> float:
        return float(self.x[0, 0])

    @property
    def velocity(self) -> float:
        return float(self.x[1, 0])
