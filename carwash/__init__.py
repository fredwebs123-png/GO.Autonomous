"""GO Autonomous - camera-guided car wash conveyor positioning.

Shared building blocks used by run_guidance.py (single camera) and
car_wash_guidance_dual_camera.py:

    calibration  GroundPlaneCalibrator  pixels -> inches on the ground
    detection    Detection, WheelDetector, RedCarCropper
    tracking     PositionKalmanFilter
    guidance     GuidanceStateMachine, GuidanceState, signal names
    outputs      ConsoleOutput, AvatarOutput, ArduinoOutput, OutputHub
    overlay      draw_overlay (debug view)

Modules are imported on demand so the pure-logic parts (guidance, tracking)
work without OpenCV or ultralytics installed.
"""
