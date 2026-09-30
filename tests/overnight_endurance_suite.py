"""DRISHTI AI - Comprehensive Overnight Endurance & Soak Testing Suite.

Engineered for unattended multi-hour (e.g., 8-hour) continuous validation:
1. Prevents Windows OS from sleeping via Win32 SetThreadExecutionState.
2. Exercises the complete DMS perception pipeline (MediaPipe + Hugging Face Transformers + Safety Core).
3. Injects diverse inputs: real dataset images, synthetic frames, and adversarial corruptions.
4. Continuous memory profiling (tracemalloc) and leak detection.
5. Continuously updates live JSON and Markdown reports for morning inspection.
6. Graceful shutdown on Ctrl+C / SIGINT with comprehensive post-mortem summary.
"""

from __future__ import annotations

import argparse
import datetime
import gc
import json
import os
from pathlib import Path
import random
import signal
import sys
import time
import traceback
import tracemalloc
from typing import Dict, List, Optional

import cv2
import numpy as np

# Windows Keep-Awake Flags
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040
ES_CONTINUOUS = 0x80000000

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_tracking.driver_monitor import DrishtiAIDMS, EdgeAIClassifier
from ai_tracking.safety_core import DriverBehaviorMonitor, DriverBehaviorSignal


class WindowsPowerLock:
    """Acquires Win32 power execution state to prevent sleep during overnight testing."""

    def __init__(self, keep_screen_on: bool = False) -> None:
        self.keep_screen_on = keep_screen_on
        self.is_windows = sys.platform == "win32"
        self._locked = False

    def acquire(self) -> None:
        if not self.is_windows:
            return
        try:
            import ctypes
            flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            if self.keep_screen_on:
                flags |= ES_DISPLAY_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(flags)
            self._locked = True
            print("[POWER] Windows Keep-Awake lock engaged (OS sleep prevented).", flush=True)
        except Exception as exc:
            print(f"[POWER] Warning: Could not engage Win32 power lock: {exc}", flush=True)

    def release(self) -> None:
        if not self.is_windows or not self._locked:
            return
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            self._locked = False
            print("[POWER] Windows Keep-Awake lock released (normal power behavior restored).", flush=True)
        except Exception:
            pass


class OvernightEnduranceRunner:
    def __init__(
        self,
        dataset_dir: Path,
        output_dir: Path,
        duration_hours: float = 8.0,
        frames_per_cycle: int = 50,
        delay_s: float = 0.02,
        test_adversarial: bool = True,
        simulate_speed_variation: bool = True,
    ) -> None:
        self.dataset_dir = dataset_dir
        self.output_dir = output_dir
        self.duration_seconds = max(duration_hours * 3600.0, 0.0)
        self.frames_per_cycle = frames_per_cycle
        self.delay_s = delay_s
        self.test_adversarial = test_adversarial
        self.simulate_speed_variation = simulate_speed_variation

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.output_dir / "overnight_execution.log"
        self.status_file = self.output_dir / "overnight_status.json"
        self.report_file = self.output_dir / "OVERNIGHT_REPORT.md"

        self.samples: List[Path] = []
        self._load_samples()

        print("[INIT] Initializing DRISHTI AI Perception & Hugging Face Engine...", flush=True)
        self.dms = DrishtiAIDMS()
        self.safety_monitor = DriverBehaviorMonitor()
        self.edge_classifier = EdgeAIClassifier()

        # Telemetry metrics
        self.start_time = 0.0
        self.total_frames = 0
        self.total_errors = 0
        self.total_cycles = 0
        self.error_log: List[Dict[str, object]] = []
        self.class_counts: Dict[str, int] = {}
        self.initial_mem_mb = 0.0
        self.peak_mem_mb = 0.0
        self.current_mem_mb = 0.0
        self.current_rss_mb = 0.0
        self.peak_rss_mb = 0.0
        self.fps_history: List[float] = []
        self._stop_requested = False

        # Register signals
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"\n[INTERRUPT] Received signal {signum}. Finalizing report...", flush=True)
        self._stop_requested = True

    def _load_samples(self) -> None:
        if self.dataset_dir.exists():
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                self.samples.extend(self.dataset_dir.rglob(ext))
        print(f"[INIT] Discovered {len(self.samples)} sample images from '{self.dataset_dir}'.", flush=True)

    def log(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted, flush=True)
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass

    def warmup(self, timeout_s: float = 40.0) -> None:
        print("[WARMUP] Warming up Hugging Face Transformer and MediaPipe...", flush=True)
        start = time.time()
        while time.time() - start < timeout_s:
            if self.dms.hf_driver._classifier is not None or self.dms.hf_driver._load_error:
                break
            time.sleep(0.5)
        backend = getattr(self.dms.hf_driver, "_backend", "unknown")
        print(f"[WARMUP] Complete. Hugging Face backend: {backend}.", flush=True)

    def _generate_adversarial_frame(self, index: int) -> np.ndarray:
        scenario = index % 7
        if scenario == 0:
            return np.zeros((480, 640, 3), dtype=np.uint8)  # Pitch black
        elif scenario == 1:
            return np.full((480, 640, 3), 255, dtype=np.uint8)  # Glare / whiteout
        elif scenario == 2:
            return np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)  # Noise
        elif scenario == 3:
            return np.random.randint(50, 180, (120, 160, 3), dtype=np.uint8)  # Low-res
        elif scenario == 4:
            f = np.zeros((1080, 1920, 3), dtype=np.uint8)  # 1080p HD
            cv2.circle(f, (960, 540), 200, (180, 150, 120), -1)
            return f
        elif scenario == 5:
            return np.full((480, 640, 3), (255, 0, 0), dtype=np.uint8)  # Color tint
        else:
            # Contrast inversion
            img = np.full((480, 640, 3), 128, dtype=np.uint8)
            cv2.rectangle(img, (200, 150), (440, 330), (0, 0, 255), -1)
            return img

    def _fetch_frame(self, iteration: int) -> np.ndarray:
        if self.test_adversarial and iteration % 6 == 0:
            return self._generate_adversarial_frame(iteration)
        if self.samples:
            path = random.choice(self.samples)
            frame = cv2.imread(str(path))
            if frame is not None:
                return frame
        # Synthetic fallback
        canvas = np.full((480, 640, 3), (35, 35, 45), dtype=np.uint8)
        cv2.ellipse(canvas, (320, 240), (100, 140), 0, 0, 360, (170, 190, 220), -1)
        return canvas

    def _save_live_state(self, is_complete: bool = False, status_label: str = "RUNNING") -> None:
        elapsed = time.time() - self.start_time
        avg_fps = self.total_frames / max(elapsed, 0.001)
        recent_fps = (sum(self.fps_history[-10:]) / len(self.fps_history[-10:])) if self.fps_history else avg_fps

        data = {
            "status": status_label,
            "is_complete": is_complete,
            "start_time": datetime.datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "target_duration_seconds": self.duration_seconds,
            "progress_percent": round(min(100.0, (elapsed / self.duration_seconds) * 100.0), 1) if self.duration_seconds > 0 else "N/A (Infinite)",
            "total_cycles": self.total_cycles,
            "total_frames": self.total_frames,
            "current_fps": round(recent_fps, 2),
            "avg_fps": round(avg_fps, 2),
            "initial_mem_mb": round(self.initial_mem_mb, 2),
            "current_mem_mb": round(self.current_mem_mb, 2),
            "peak_mem_mb": round(self.peak_mem_mb, 2),
            "memory_growth_mb": round(self.current_mem_mb - self.initial_mem_mb, 2),
            "rss_mem_mb": round(self.current_rss_mb, 2),
            "peak_rss_mb": round(self.peak_rss_mb, 2),
            "total_errors": self.total_errors,
            "huggingface_classes": self.class_counts,
            "recent_errors": self.error_log[-5:],
        }

        try:
            with self.status_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

        # Write Markdown Report
        md_lines = [
            "# DRISHTI AI - Overnight Soak & Stability Test Report",
            f"\n**Status**: `{status_label}` | **Last Updated**: `{data['last_updated']}`",
            "\n## 1. Executive Summary",
            f"- **Start Time**: {data['start_time']}",
            f"- **Elapsed Time**: {datetime.timedelta(seconds=int(elapsed))} ({data['progress_percent']}% of target)",
            f"- **Total Frames Processed**: {self.total_frames:,}",
            f"- **Average Throughput**: {data['avg_fps']} FPS",
            f"- **Total Errors / Crashes**: **{self.total_errors}**",
            "\n## 2. Memory & Stability Diagnostics",
            "| Metric | Initial Value | Current Value | Peak Recorded | Net Delta |",
            "| :--- | :--- | :--- | :--- | :--- |",
            f"| **Heap RAM (Tracemalloc)** | {data['initial_mem_mb']} MB | {data['current_mem_mb']} MB | {data['peak_mem_mb']} MB | {data['memory_growth_mb']} MB |",
            f"| **Physical Process RSS** | - | {data['rss_mem_mb']} MB | {data['peak_rss_mb']} MB | - |",
            "\n## 3. Hugging Face Inference Telemetry",
            "| Detected State Class | Frame Inferences Count |",
            "| :--- | :--- |",
        ]
        for cls_name, count in sorted(self.class_counts.items(), key=lambda x: -x[1]):
            md_lines.append(f"| `{cls_name}` | {count:,} |")

        md_lines.append("\n## 4. Error & Crash Log")
        if not self.error_log:
            md_lines.append("✅ **Zero crashes or unhandled exceptions detected.** Pipeline is 100% stable.")
        else:
            md_lines.append(f"⚠️ **Recorded {len(self.error_log)} exception(s):**")
            for err in self.error_log[-10:]:
                md_lines.append(f"- Frame #{err.get('frame')}: `{err.get('error')}`")

        md_lines.append("\n---\n*Auto-generated by DRISHTI AI Overnight Endurance Suite.*")

        try:
            with self.report_file.open("w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))
        except Exception:
            pass

    def run(self) -> bool:
        power = WindowsPowerLock()
        power.acquire()

        self.warmup()
        tracemalloc.start()
        self.start_time = time.time()
        self.initial_mem_mb, _ = [m / (1024 * 1024) for m in tracemalloc.get_traced_memory()]

        duration_desc = f"{self.duration_seconds / 3600.0:.1f} hours" if self.duration_seconds > 0 else "Infinite Loop (until manual stop)"
        self.log(
            f"==========================================================\n"
            f"    STARTING DRISHTI AI OVERNIGHT ENDURANCE TEST\n"
            f"==========================================================\n"
            f"Target Duration:    {duration_desc}\n"
            f"Frames per Batch:   {self.frames_per_cycle}\n"
            f"Artificial Delay:   {self.delay_s}s per frame\n"
            f"Adversarial Stress: {self.test_adversarial}\n"
            f"Log Output:         {self.log_file}\n"
            f"Live Report:        {self.report_file}\n"
            f"=========================================================="
        )

        try:
            while not self._stop_requested:
                elapsed = time.time() - self.start_time
                if self.duration_seconds > 0 and elapsed >= self.duration_seconds:
                    self.log("[COMPLETE] Target duration reached successfully.")
                    break

                self.total_cycles += 1
                cycle_start = time.time()
                cycle_errors = 0

                for _ in range(self.frames_per_cycle):
                    if self._stop_requested:
                        break

                    self.total_frames += 1
                    speed = 60.0 + (random.uniform(-20.0, 40.0) if self.simulate_speed_variation else 0.0)

                    try:
                        frame = self._fetch_frame(self.total_frames)

                        # 1. Perception & Hugging Face pipeline
                        dms_status = self.dms.process_frame(frame, speed_kph=speed)
                        assert isinstance(dms_status, dict)

                        hf = dms_status.get("huggingface") or {}
                        label = str(hf.get("label") or "UNKNOWN")
                        self.class_counts[label] = self.class_counts.get(label, 0) + 1

                        # 2. Safety decision core
                        signal = DriverBehaviorSignal(
                            driver_id=str(dms_status.get("driver_id", "drv_overnight")),
                            vehicle_id="veh_fleet_01",
                            drowsiness_score=0.95 if dms_status.get("drowsy") else 0.05,
                            distraction_score=0.9 if dms_status.get("distracted") else 0.05,
                            yawning_score=0.85 if dms_status.get("yawning") else 0.05,
                            phone_usage_score=float(dms_status.get("phone_usage_score", 0.0)),
                            speed_kph=speed,
                            timestamp_ms=int(time.time() * 1000),
                            main_ai_model="Hugging Face",
                            hf_state=label,
                            hf_confidence=float(hf.get("score") or 0.0),
                        )
                        assessment = self.safety_monitor.evaluate(signal, now_ms=int(time.time() * 1000))
                        assert assessment.risk_level is not None

                        if self.delay_s > 0:
                            time.sleep(self.delay_s)

                    except Exception as exc:
                        cycle_errors += 1
                        self.total_errors += 1
                        tb = traceback.format_exc()
                        self.error_log.append({
                            "frame": self.total_frames,
                            "cycle": self.total_cycles,
                            "error": str(exc),
                            "traceback": tb,
                        })
                        self.log(f"[EXCEPTION Frame #{self.total_frames}]: {exc}")

                # Cycle stats
                cycle_dur = time.time() - cycle_start
                cycle_fps = self.frames_per_cycle / max(cycle_dur, 0.001)
                self.fps_history.append(cycle_fps)
                if len(self.fps_history) > 50:
                    self.fps_history.pop(0)

                self.current_mem_mb, self.peak_mem_mb = [m / (1024 * 1024) for m in tracemalloc.get_traced_memory()]
                try:
                    import psutil
                    self.current_rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                    self.peak_rss_mb = max(self.peak_rss_mb, self.current_rss_mb)
                except Exception:
                    self.current_rss_mb = self.current_mem_mb

                # Periodic Garbage Collection diagnostic every 10 cycles
                if self.total_cycles % 10 == 0:
                    gc.collect()
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass

                self.log(
                    f"[CYCLE {self.total_cycles:4d}] "
                    f"Frames: {self.total_frames:6d} | "
                    f"Speed: {cycle_fps:5.1f} FPS | "
                    f"Heap: {self.current_mem_mb:5.1f}MB | RSS: {self.current_rss_mb:5.1f}MB | "
                    f"Errors: {self.total_errors}"
                )

                # Persist live state
                self._save_live_state(is_complete=False, status_label="RUNNING")

        except Exception as fatal_exc:
            self.log(f"[FATAL ERROR]: {fatal_exc}\n{traceback.format_exc()}")
            self.total_errors += 1
        finally:
            status_text = "COMPLETED" if (self.duration_seconds > 0 and time.time() - self.start_time >= self.duration_seconds) else "INTERRUPTED"
            self._save_live_state(is_complete=True, status_label=status_text)
            tracemalloc.stop()
            power.release()

            total_elapsed = time.time() - self.start_time
            avg_fps = self.total_frames / max(total_elapsed, 0.001)

            self.log(
                f"\n==========================================================\n"
                f"   DRISHTI AI OVERNIGHT TEST EXECUTION SUMMARY\n"
                f"==========================================================\n"
                f"Status:             {status_text}\n"
                f"Total Frames:       {self.total_frames}\n"
                f"Total Duration:     {total_elapsed / 3600.0:.2f} hours ({total_elapsed:.1f}s)\n"
                f"Average FPS:        {avg_fps:.2f}\n"
                f"Initial Memory:     {self.initial_mem_mb:.2f} MB\n"
                f"Final Memory:       {self.current_mem_mb:.2f} MB\n"
                f"Peak Memory:        {self.peak_mem_mb:.2f} MB\n"
                f"Net Memory Delta:   {self.current_mem_mb - self.initial_mem_mb:.2f} MB\n"
                f"Class Predictions:  {self.class_counts}\n"
                f"Total Exceptions:   {self.total_errors}\n"
                f"Report File:        {self.report_file}\n"
                f"=========================================================="
            )

        return self.total_errors == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DRISHTI AI Overnight Endurance Testing Suite")
    parser.add_argument("--duration-hours", type=float, default=8.0, help="Target duration in hours (0 for infinite loop)")
    parser.add_argument("--frames-per-cycle", type=int, default=50, help="Frames per cycle batch")
    parser.add_argument("--delay", type=float, default=0.02, help="Artificial delay between frames (seconds)")
    parser.add_argument("--no-adversarial", action="store_true", help="Disable adversarial frame injection")
    parser.add_argument("--dataset-dir", default="dataset", help="Path to sample dataset")
    parser.add_argument("--output-dir", default="artifacts/soak_tests", help="Directory for logs and reports")
    args = parser.parse_args()

    runner = OvernightEnduranceRunner(
        dataset_dir=Path(args.dataset_dir),
        output_dir=Path(args.output_dir),
        duration_hours=args.duration_hours,
        frames_per_cycle=args.frames_per_cycle,
        delay_s=args.delay,
        test_adversarial=not args.no_adversarial,
    )

    success = runner.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
