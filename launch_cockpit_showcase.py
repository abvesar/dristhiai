"""DRISHTI AI — Commercial Vehicle Cockpit & Dual-Screen Showcase Launcher.

Starts the central vehicle hub (app.py) and launches the full-screen Commercial
Cockpit UI in the default browser. Prints the mobile QR/URL connection details
for the evaluator's smartphone or tablet.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def main():
    python_exe = sys.executable
    port = int(os.environ.get("DRISHTI_PORT", "5000"))
    local_ip = get_local_ip()

    cockpit_url = f"http://localhost:{port}/"
    control_room_url = f"http://{local_ip}:{port}/control-room"

    print("\n" + "=" * 72)
    print("      DRISHTI AI -- COMMERCIAL VEHICLE COCKPIT & DUAL-SCREEN SHOWCASE")
    print("=" * 72)
    print("  [SCREEN 1: THE TRUCK CAB (This Laptop)]")
    print(f"  * Cockpit Cluster URL:  {cockpit_url}")
    print("  * Controls:             [W]/[Up] Accel | [S]/[Down] Brake | [Space] Emergency Stop")
    print("                          [1] 60 km/h Cruise | [2] 85 km/h Overspeed")
    print("\n  [SCREEN 2: FLEET OPERATIONS CONTROL ROOM (Evaluator's Phone/Tablet)]")
    print(f"  * Mobile URL:           {control_room_url}")
    print("  * Features:             Live Video | Biometric Gauges | In-Cab Remote Buzzer")
    print("                          Mobile Haptic Vibration Alert | AIS-140 Compliance Log")
    print("=" * 72)
    print("\nStarting vehicle hub server...")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Start Flask app
    proc = subprocess.Popen(
        [python_exe, "-u", "app.py"],
        env=env,
    )

    # Allow Flask 1.5 seconds to bind before opening browser
    def open_browser():
        time.sleep(1.8)
        print(f"\nOpening Commercial Truck Cockpit on laptop: {cockpit_url}")
        webbrowser.open(cockpit_url)

    import threading
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[!] Shutting down DRISHTI AI Commercial Showcase...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[✓] Clean shutdown complete.")


if __name__ == "__main__":
    main()
