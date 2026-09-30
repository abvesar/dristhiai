"""DRISHTI AI - Autonomous Soak Test Monitor & Auto-Recovery Watchdog.

Monitors the overnight endurance test suite process and status:
1. Detects unexpected terminations, crashes, or unhandled exceptions.
2. Automatically cleans up zombie resources and relaunches the test with remaining time.
3. Emits live heartbeats and logs to 'artifacts/soak_tests/watchdog.log'.
4. Terminates cleanly once the target 8-hour soak test is officially completed.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Dict, List, Optional

import psutil

# Enforce UTF-8 on Windows consoles to prevent cp1252 charmap crashes
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUITE_SCRIPT = PROJECT_ROOT / "tests" / "overnight_endurance_suite.py"
SOAK_DIR = PROJECT_ROOT / "artifacts" / "soak_tests"
STATUS_FILE = SOAK_DIR / "overnight_status.json"
WATCHDOG_LOG = SOAK_DIR / "watchdog.log"
WATCHDOG_STATUS = SOAK_DIR / "watchdog_status.json"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON_BIN = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable


class SoakWatchdog:
    def __init__(self, target_hours: float = 8.0, check_interval_s: float = 10.0) -> None:
        self.target_hours = target_hours
        self.check_interval_s = check_interval_s
        self.restarts_count = 0
        self.last_heartbeat_time = 0.0
        self._stop_requested = False

        SOAK_DIR.mkdir(parents=True, exist_ok=True)

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        self.log(f"[WATCHDOG] Received shutdown signal ({signum}). Exiting watchdog...")
        self._stop_requested = True

    def log(self, message: str) -> None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}"
        try:
            print(line, flush=True)
        except Exception:
            try:
                clean_line = line.encode("ascii", errors="replace").decode("ascii")
                print(clean_line, flush=True)
            except Exception:
                pass
        try:
            with WATCHDOG_LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def find_suite_processes(self) -> List[psutil.Process]:
        """Finds all running processes executing overnight_endurance_suite.py."""
        found = []
        my_pid = os.getpid()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.pid == my_pid:
                    continue
                cmdline = p.info.get("cmdline") or []
                cmd_str = " ".join(cmdline).lower()
                if "overnight_endurance_suite.py" in cmd_str:
                    found.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return found

    def read_suite_status(self) -> Dict[str, object]:
        if not STATUS_FILE.is_file():
            return {}
        try:
            with STATUS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def write_watchdog_state(self, is_alive: bool, pids: List[int], suite_data: Dict[str, object]) -> None:
        state = {
            "watchdog_active": not self._stop_requested,
            "last_check": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "suite_alive": is_alive,
            "active_pids": pids,
            "restarts_count": self.restarts_count,
            "suite_progress_percent": suite_data.get("progress_percent", 0.0),
            "suite_frames": suite_data.get("total_frames", 0),
            "suite_errors": suite_data.get("total_errors", 0),
            "suite_status": suite_data.get("status", "UNKNOWN"),
        }
        try:
            with WATCHDOG_STATUS.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def relaunch_suite(self, remaining_hours: float) -> Optional[subprocess.Popen]:
        self.log(
            f"==========================================================\n"
            f"[WATCHDOG ACTION] Relaunching Soak Test ({remaining_hours:.2f}h remaining)\n"
            f"Restart count: {self.restarts_count + 1}\n"
            f"Binary: {PYTHON_BIN}\n"
            f"=========================================================="
        )
        self.restarts_count += 1
        time.sleep(3.0)  # Grace period for Windows handles to release

        # Clean any zombie processes
        for p in self.find_suite_processes():
            try:
                p.kill()
            except Exception:
                pass

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            proc = subprocess.Popen(
                [
                    PYTHON_BIN,
                    str(SUITE_SCRIPT),
                    "--duration-hours",
                    str(remaining_hours),
                ],
                cwd=str(PROJECT_ROOT),
                env=env,
                creationflags=creation_flags,
            )
            self.log(f"[WATCHDOG SUCCESS] Spawned new test instance (PID: {proc.pid}).")
            return proc
        except Exception as exc:
            self.log(f"[WATCHDOG ERROR] Failed to relaunch test process: {exc}")
            return None

    def run(self) -> None:
        self.log("=" * 60)
        self.log("  DRISHTI AI -- SOAK TEST WATCHDOG & AUTO-RECOVERY ACTIVE")
        self.log(f"  Target Duration: {self.target_hours} Hours")
        self.log(f"  Check Interval:  {self.check_interval_s}s")
        self.log("=" * 60)

        while not self._stop_requested:
            procs = self.find_suite_processes()
            suite_data = self.read_suite_status()
            pids = [p.pid for p in procs]

            is_alive = len(procs) > 0
            is_complete = bool(suite_data.get("is_complete", False))
            status_text = str(suite_data.get("status", "")).upper()
            now = time.time()

            # Heartbeat logging every 60 seconds
            if now - self.last_heartbeat_time >= 60.0:
                self.last_heartbeat_time = now
                mem_str = ""
                if is_alive:
                    try:
                        total_rss = sum(p.memory_info().rss for p in procs) / (1024 * 1024)
                        mem_str = f" | Total RSS: {total_rss:.1f} MB"
                    except Exception:
                        pass

                self.log(
                    f"[HEARTBEAT] Suite Active: {is_alive} (PIDs: {pids}) | "
                    f"Frames: {suite_data.get('total_frames', 0)} | "
                    f"Progress: {suite_data.get('progress_percent', 0)}% | "
                    f"Errors: {suite_data.get('total_errors', 0)}{mem_str}"
                )

            self.write_watchdog_state(is_alive, pids, suite_data)

            if is_alive:
                # Test is actively running
                time.sleep(self.check_interval_s)
                continue

            # Process is not running!
            if is_complete and status_text == "COMPLETED":
                self.log("[WATCHDOG COMPLETE] Overnight test achieved its target duration successfully.")
                break

            # Unexpected termination / crash detected
            elapsed_s = float(suite_data.get("elapsed_seconds") or 0.0)
            target_s = float(suite_data.get("target_duration_seconds") or (self.target_hours * 3600.0))
            remaining_s = max(1800.0, target_s - elapsed_s)
            remaining_h = round(remaining_s / 3600.0, 2)

            self.log(
                f"[WATCHDOG ALERT] Soak test process terminated unexpectedly! "
                f"(Status in JSON: '{status_text}', Elapsed: {elapsed_s:.1f}s). "
                f"Auto-recovery engaged."
            )

            self.relaunch_suite(remaining_h)
            time.sleep(10.0)

        self.log("[WATCHDOG] Monitor stopped cleanly.")


def main():
    watchdog = SoakWatchdog(target_hours=8.0, check_interval_s=10.0)
    watchdog.run()


if __name__ == "__main__":
    main()
