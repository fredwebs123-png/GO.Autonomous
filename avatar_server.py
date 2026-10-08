"""
Avatar guidance server - serves avatar_display.html and a tiny local API.
The pipeline (run_guidance.py) POSTs the same signal strings it would send
to the Arduino sign, and the avatar on the monitor updates in real time.

Usage (PowerShell, from the project folder):
  python avatar_server.py          # driven by run_guidance.py
  python avatar_server.py --demo   # cycles through every signal, no pipeline needed
Then open http://localhost:8000 in a browser (F11 for full screen).

Fail-safe: if no update arrives for STALE_AFTER_S seconds (pipeline crashed,
frozen or stopped), /status reports WAIT instead of the last signal. The
pipeline re-sends its signal every 0.5 s as a heartbeat.

API:
  POST /update  {"signal": "MOVE_LEFT"}
  GET  /status  -> {"signal": "...", "stale": false}
  GET  /assets/<file>  -> files from avatar_assets/ (3D model, three.js)
"""

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8000
HTML_FILE = Path(__file__).parent / "avatar_display.html"
ASSET_DIR = (Path(__file__).parent / "avatar_assets").resolve()
ASSET_TYPES = {
    ".js": "text/javascript", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
    ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".bin": "application/octet-stream",
    ".webm": "video/webm", ".mp4": "video/mp4", ".json": "application/json",
}
STALE_AFTER_S = 2.0
VALID_SIGNALS = {"MOVE_LEFT", "MOVE_RIGHT", "STRAIGHT", "STOP", "CONVEYOR_MOVING", "WAIT"}

current_signal = "WAIT"
last_update = 0.0
lock = threading.Lock()


def set_signal(signal):
    global current_signal, last_update
    if signal not in VALID_SIGNALS:
        signal = "WAIT"  # unknown -> fail-safe
    with lock:
        current_signal = signal
        last_update = time.monotonic()


def get_status():
    with lock:
        stale = time.monotonic() - last_update > STALE_AFTER_S
        return {"signal": "WAIT" if stale else current_signal, "stale": stale}


class AvatarHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet the default request logging

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_html()
        elif self.path == "/status":
            self._send_json(get_status())
        elif self.path.startswith("/assets/"):
            self._serve_asset(self.path[len("/assets/"):].split("?")[0])
        else:
            self.send_error(404)

    def _serve_asset(self, rel):
        target = (ASSET_DIR / rel).resolve()
        # Only files inside avatar_assets/ with a known type - nothing else on the PC.
        if ASSET_DIR not in target.parents or target.suffix.lower() not in ASSET_TYPES or not target.is_file():
            self.send_error(404)
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ASSET_TYPES[target.suffix.lower()])
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if self.path != "/update":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
            set_signal(str(data.get("signal", "WAIT")))
            self.send_response(200)
            self.end_headers()
        except Exception as e:  # noqa: BLE001
            self.send_error(400, str(e))

    def _serve_html(self):
        try:
            content = HTML_FILE.read_bytes()
        except FileNotFoundError:
            self.send_error(500, f"{HTML_FILE.name} not found next to this script")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, obj):
        payload = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


def run_demo():
    """Cycles through every signal so the avatar can be checked standalone."""
    demo_signals = ["MOVE_LEFT", "MOVE_RIGHT", "STRAIGHT", "STOP", "CONVEYOR_MOVING", "WAIT"]
    while True:
        for signal in demo_signals:
            print(f"Demo: showing {signal}")
            end = time.monotonic() + 3
            while time.monotonic() < end:
                set_signal(signal)  # keep the heartbeat fresh
                time.sleep(0.5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="cycle through every signal")
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()

    # Windows lets two servers share a port when address reuse is on, which
    # would let a stray --demo server mix signals into the real one.
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        server = ThreadingHTTPServer(("localhost", args.port), AvatarHandler)
    except OSError:
        raise SystemExit(f"Port {args.port} is already in use - another avatar server is running. Close it first.")
    print(f"Avatar server running at http://localhost:{args.port}  (Ctrl+C to stop)")
    if args.demo:
        print("Demo mode ON - cycling through signals every 3 seconds.")
        threading.Thread(target=run_demo, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
