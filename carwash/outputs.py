"""Guidance outputs. Every output takes the same signal strings (see guidance.py).

OutputHub sends a signal when it changes and re-sends it every
`resend_interval_s` as a heartbeat. The avatar server and the Arduino sketch
fall back to WAIT if the heartbeat stops, so a crashed or frozen pipeline
can never leave a stale "go" signal on screen.

A failing output (avatar server not running, Arduino unplugged) is logged
and skipped; it never crashes the guidance loop.
"""

import json
import time
import urllib.request


class ConsoleOutput:
    name = "console"

    def send(self, signal):
        print(f"[signal] {signal}")

    def close(self):
        pass


class AvatarOutput:
    name = "avatar"

    def __init__(self, url: str = "http://localhost:8000/update", timeout_s: float = 0.25):
        self.url = url
        self.timeout_s = timeout_s

    def send(self, signal):
        body = json.dumps({"signal": signal}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_s):
            pass

    def close(self):
        pass


class ArduinoOutput:
    name = "arduino"

    def __init__(self, port: str = "COM6", baud: int = 9600):
        import serial  # pyserial

        # Close the Arduino IDE Serial Monitor first - only one program can hold the port.
        self.ser = serial.Serial(port, baud, timeout=0)
        time.sleep(2)  # opening the port resets the Uno; LEDs flash briefly, that's normal

    def send(self, signal):
        self.ser.write((signal + "\n").encode())
        self.ser.reset_input_buffer()  # discard the sketch's "Received:" echo

    def close(self):
        try:
            self.ser.write(b"WAIT\n")
        finally:
            self.ser.close()


class OutputHub:
    def __init__(self, outputs, resend_interval_s: float = 0.5):
        self.outputs = list(outputs)
        self.resend_interval_s = resend_interval_s
        self._last_signal = None
        self._last_sent_at = 0.0
        self._failing = set()

    def send(self, signal, now: float | None = None):
        now = time.monotonic() if now is None else now
        changed = signal != self._last_signal
        if not changed and now - self._last_sent_at < self.resend_interval_s:
            return False
        for out in self.outputs:
            if out.name == "console" and not changed:
                continue  # print changes only, not heartbeats
            try:
                out.send(signal)
                if out.name in self._failing:
                    self._failing.discard(out.name)
                    print(f"[output] {out.name} recovered")
            except Exception as e:  # noqa: BLE001 - a dead output must never crash the loop
                if out.name not in self._failing:
                    self._failing.add(out.name)
                    print(f"[output] {out.name} failed ({e}); will keep retrying quietly")
        self._last_signal = signal
        self._last_sent_at = now
        return True

    def close(self):
        for out in self.outputs:
            try:
                out.close()
            except Exception:  # noqa: BLE001
                pass


def build_outputs(cfg: dict) -> OutputHub:
    """Build an OutputHub from the "outputs" section of the config."""
    outs = []
    if cfg.get("console", True):
        outs.append(ConsoleOutput())
    avatar = cfg.get("avatar", {})
    if avatar.get("enabled"):
        outs.append(AvatarOutput(avatar.get("url", "http://localhost:8000/update")))
    arduino = cfg.get("arduino", {})
    if arduino.get("enabled"):
        try:
            outs.append(ArduinoOutput(arduino.get("port", "COM6"), arduino.get("baud", 9600)))
        except Exception as e:  # noqa: BLE001
            print(f"[output] Arduino not available on {arduino.get('port')}: {e}")
    return OutputHub(outs, cfg.get("resend_interval_s", 0.5))
