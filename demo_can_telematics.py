"""DRISHTI AI — Terminal CAN-Bus Telematics Controller.

Allows live modulation of vehicle speed and driver distraction over the CAN-bus
interface to demonstrate risk escalation (Demo 3) and satellite failover (Demo 2).

Controls:
  [Up Arrow]    / [W]: Accelerate (+5 km/h)
  [Down Arrow]  / [S]: Decelerate (-5 km/h)
  [1]                : Set Speed to 60 km/h (Normal Mountain Speed)
  [2]                : Set Speed to 85 km/h (Overspeed - Escalates Risk past 80 km/h)
  [Ctrl+C]           : Exit
"""

import json
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import msvcrt
except ImportError:
    msvcrt = None


def send_speed(delta=None, speed=None, port=5000):
    url = f"http://127.0.0.1:{port}/api/speed"
    body = {}
    if delta is not None:
        body["delta"] = delta
    if speed is not None:
        body["speed"] = speed
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception as exc:
        return {"error": str(exc)}


def main():
    port = 5000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    print("\n" + "=" * 65)
    print("     DRISHTI AI -- CAN-BUS TELEMATICS TERMINAL CONTROLLER")
    print("=" * 65)
    print(f" Target Dashboard: http://127.0.0.1:{port}/api/speed")
    print(" Controls:")
    print("   * [Up Arrow] or [W]   : Accelerate (+5 km/h)")
    print("   * [Down Arrow] or [S] : Decelerate (-5 km/h)")
    print("   * [1]                 : Cruising Speed (60 km/h)")
    print("   * [2]                 : Overspeed (85 km/h) -> Escalates to HIGH Risk")
    print("   * [Ctrl+C] or [Q]     : Exit")
    print("=" * 65 + "\n")

    if msvcrt is None:
        print("[!] msvcrt is only available on Windows. Exiting.")
        return 1

    current_speed = 60.0
    res = send_speed(speed=current_speed, port=port)
    if "error" in res:
        print(f"[!] Warning: Could not reach {port} yet ({res['error']}). Start app.py first.")
    else:
        print(f"[CAN] Initialized vehicle speed: {res.get('speed_kph', current_speed)} km/h")

    try:
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in {"\x00", "\xe0"}:
                    key = msvcrt.getwch()

                if key in {"H", "w", "W"}:
                    res = send_speed(delta=5, port=port)
                    speed = res.get("speed_kph", "N/A")
                    flag = "🚨 [OVERSPEED >= 80 km/h: SATELLITE DISPATCH ARMED]" if res.get("overspeed") else ""
                    print(f"  ▲ Throttle Up   -> Speed: {speed} km/h {flag}")
                elif key in {"P", "s", "S"}:
                    res = send_speed(delta=-5, port=port)
                    speed = res.get("speed_kph", "N/A")
                    print(f"  ▼ Decelerate    -> Speed: {speed} km/h")
                elif key == "1":
                    res = send_speed(speed=60, port=port)
                    print("  ⚡ Cruising Set -> Speed: 60 km/h [NORMAL SPEED]")
                elif key == "2":
                    res = send_speed(speed=85, port=port)
                    print("  ⚡ Overspeed Set-> Speed: 85 km/h 🚨 [OVERSPEED >= 80 km/h: SATELLITE DISPATCH ARMED]")
                elif key in {"q", "Q", "\x1b"}:
                    break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass

    print("\n[CAN] Controller exited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
