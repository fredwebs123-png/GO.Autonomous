"""
Standalone Arduino/LED test - confirms the serial connection and LED sign
work correctly, independent of the camera/vision pipeline.
"""

import serial
import time

# TODO: change this to match your Arduino's port from the Arduino IDE (Tools > Port)
PORT = "COM6"
BAUD_RATE = 9600

print(f"Connecting to Arduino on {PORT}...")
arduino = serial.Serial(PORT, BAUD_RATE)
time.sleep(2)  # give the Arduino a moment after the serial connection resets it
print("Connected. Running through each signal...")

signals = ["MOVE_LEFT", "MOVE_RIGHT", "STRAIGHT", "STOP", "CONVEYOR_MOVING", "WAIT"]

for signal in signals:
    print(f"Sending: {signal}")
    arduino.write((signal + "\n").encode())
    time.sleep(0.3)
    while arduino.in_waiting:
        print("  Arduino says:", arduino.readline().decode(errors="replace").strip())
    # Hold each state ~3 s. Re-send every 0.5 s: the sketch drops to WAIT
    # if it hears nothing for 2 s (heartbeat fail-safe).
    for _ in range(5):
        time.sleep(0.5)
        arduino.write((signal + "\n").encode())
    arduino.reset_input_buffer()

print("Test complete. All LEDs should have lit up in sequence.")
arduino.close()
