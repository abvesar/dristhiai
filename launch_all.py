"""Unified Launcher for DRISHTI AI: Launches both Flask and Gradio Dashboards concurrently.

- Flask Operations Hub: http://localhost:5000/
- Gradio Telemetry UI:   http://localhost:7860/
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser


def stream_logs(pipe, prefix: str):
    """Streams child process stdout/stderr line-by-line with colored prefix."""
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            print(f"{prefix} {line.rstrip()}", flush=True)
    except Exception:
        pass


def main():
    python_exe = sys.executable
    flask_port = os.environ.get("DRISHTI_PORT", "5000")
    gradio_port = os.environ.get("GRADIO_PORT", "7860")

    print("\n" + "=" * 65)
    print("       DRISHTI AI -- DUAL DASHBOARD SYSTEM LAUNCHER")
    print("=" * 65)
    print(f" [1] Flask Operations Command:   http://localhost:{flask_port}/")
    print(f" [2] Gradio Live AI Telemetry:   http://localhost:{gradio_port}/")
    print("=" * 65)
    print(" Press Ctrl+C at any time to gracefully shut down both dashboards.\n")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # 1. Start Flask Dashboard
    flask_proc = subprocess.Popen(
        [python_exe, "-u", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # 2. Start Gradio Dashboard
    gradio_proc = subprocess.Popen(
        [python_exe, "-u", "gradio_app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # Stream logs asynchronously
    threading.Thread(target=stream_logs, args=(flask_proc.stdout, "[FLASK] "), daemon=True).start()
    threading.Thread(target=stream_logs, args=(gradio_proc.stdout, "[GRADIO]"), daemon=True).start()

    # Automatically open both browser tabs with appropriate spacing
    def open_browsers():
        time.sleep(3.0)
        print(f"\n[LAUNCHER] Opening Flask dashboard (http://localhost:{flask_port}/)...")
        webbrowser.open(f"http://localhost:{flask_port}/")
        time.sleep(6.0)
        print(f"[LAUNCHER] Opening Gradio dashboard (http://localhost:{gradio_port}/)...")
        webbrowser.open(f"http://localhost:{gradio_port}/")

    threading.Thread(target=open_browsers, daemon=True).start()

    # Monitor both processes
    try:
        while True:
            flask_code = flask_proc.poll()
            gradio_code = gradio_proc.poll()

            if flask_code is not None:
                print(f"[LAUNCHER] Flask process exited with code {flask_code}")
                break
            if gradio_code is not None:
                print(f"[LAUNCHER] Gradio process exited with code {gradio_code}")
                break

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Shutting down both dashboards gracefully...")
    finally:
        for proc, name in [(flask_proc, "Flask"), (gradio_proc, "Gradio")]:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()
        print("[LAUNCHER] All dashboards stopped cleanly. Goodbye!\n")


if __name__ == "__main__":
    main()
