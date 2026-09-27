"""Continuous Stability & Automated Stress Test Runner for DRISHTI AI.

Continuously feeds diverse real-world, synthetic, and adversarial video frames
through the complete DRISHTI AI perception, tracking, Hugging Face inference,
and safety assessment pipeline to verify zero-crash stability, memory integrity,
and execution reliability under load.
"""

from __future__ import annotations

import argparse
import datetime
import gc
import json
import os
from pathlib import Path
import random
import sys
import time
import traceback
import tracemalloc
from typing import Dict, List, Optional

import cv2
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_tracking.driver_monitor import DrishtiAIDMS, EdgeAIClassifier
from ai_tracking.safety_core import DriverBehaviorMonitor, DriverBehaviorSignal


class ContinuousStabilityTester:
    def __init__(
        self,
        dataset_dir: Path,
        log_file: Optional[Path] = None,
        test_adversarial: bool = True,
        simulate_speed_variation: bool = True,
    ) -> None:
        self.dataset_dir = dataset_dir
        self.log_file = log_file
        self.test_adversarial = test_adversarial
        self.simulate_speed_variation = simulate_speed_variation

        self.samples: List[Path] = []
        self._load_dataset_samples()

        print("[INIT] Initializing DRISHTI AI Perception & Hugging Face Engine...")
        self.dms = DrishtiAIDMS()
        self.safety_monitor = DriverBehaviorMonitor()
        self.edge_classifier = EdgeAIClassifier()

        # Stats tracking
        self.total_frames = 0
        self.total_errors = 0
        self.error_log: List[Dict[str, object]] = []
        self.class_counts: Dict[str, int] = {}
        self.start_time = 0.0

    def _load_dataset_samples(self) -> None:
        if self.dataset_dir.exists():
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                self.samples.extend(self.dataset_dir.rglob(ext))

        print(f"[INIT] Discovered {len(self.samples)} sample images in '{self.dataset_dir}'.")
        if not self.samples:
            print("[WARN] No dataset images found; generating synthetic fallback samples.")

    def warmup(self, timeout_s: float = 40.0) -> None:
        """Waits for the Hugging Face model to complete its background load."""
        print("[INIT] Waiting for primary Hugging Face transformer model to warm up...")
        start = time.time()
        while time.time() - start < timeout_s:
            if self.dms.hf_driver._classifier is not None or self.dms.hf_driver._load_error:
                break
            time.sleep(0.5)
        if self.dms.hf_driver._classifier is not None:
            print(f"[INIT] Hugging Face model loaded successfully ({self.dms.hf_driver._backend}).")
        elif self.dms.hf_driver._load_error:
            print(f"[WARN] Hugging Face load notice: {self.dms.hf_driver._load_error}")
        else:
            print("[WARN] Model still loading in background; proceeding with initial frames.")

    def _generate_adversarial_frame(self, index: int) -> np.ndarray:
        """Generates challenging edge-case frames to stress-test numerical bounds."""
        scenario = index % 6
        if scenario == 0:
            # Completely pitch black frame
            return np.zeros((480, 640, 3), dtype=np.uint8)
        elif scenario == 1:
            # High-intensity glare / pure whiteout
            return np.full((480, 640, 3), 255, dtype=np.uint8)
        elif scenario == 2:
            # Random high-frequency Gaussian noise
            return np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        elif scenario == 3:
            # Ultra-low resolution (aspect ratio stress)
            return np.random.randint(40, 200, (160, 120, 3), dtype=np.uint8)
        elif scenario == 4:
            # High definition 1080p frame
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            cv2.circle(frame, (960, 540), 200, (180, 150, 120), -1)
            return frame
        else:
            # Severe color-shifted frame
            frame = np.full((480, 640, 3), (255, 0, 0), dtype=np.uint8)
            return frame

    def _fetch_test_frame(self, iteration: int) -> np.ndarray:
        # Every 7th frame, inject an adversarial / edge-case frame if enabled
        if self.test_adversarial and iteration % 7 == 0:
            return self._generate_adversarial_frame(iteration)

        if self.samples:
            img_path = random.choice(self.samples)
            frame = cv2.imread(str(img_path))
            if frame is not None:
                return frame

        # Synthetic fallback face frame
        canvas = np.full((480, 640, 3), (30, 30, 40), dtype=np.uint8)
        cv2.ellipse(canvas, (320, 240), (100, 140), 0, 0, 360, (160, 180, 210), -1)
        return canvas

    def log(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)
        if self.log_file:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with self.log_file.open("a", encoding="utf-8") as f:
                    f.write(formatted + "\n")
            except Exception:
                pass

    def run(self, cycles: int = 20, frames_per_cycle: int = 50, delay_s: float = 0.0) -> bool:
        """Executes automated continuous testing across cycles.
        
        Args:
            cycles: Number of testing cycles to run (0 for infinite loop until interrupted).
            frames_per_cycle: Frames to process in each cycle before reporting health telemetry.
            delay_s: Sleep delay in seconds between frames (0 for maximum CPU stress).
        
        Returns:
            True if all cycles completed without crashes, False if any unhandled error occurred.
        """
        self.warmup()
        tracemalloc.start()
        self.start_time = time.time()
        infinite = (cycles <= 0)
        cycle_idx = 0

        self.log(
            f"=== STARTING DRISHTI AI CONTINUOUS STABILITY SOAK TEST ===\n"
            f"Mode: {'Infinite Soak' if infinite else f'{cycles} cycles x {frames_per_cycle} frames ({cycles * frames_per_cycle} total)'} | "
            f"Adversarial Testing: {self.test_adversarial} | Delay: {delay_s}s"
        )

        try:
            while infinite or cycle_idx < cycles:
                cycle_idx += 1
                cycle_start_time = time.time()
                cycle_errors = 0

                for f_idx in range(frames_per_cycle):
                    self.total_frames += 1
                    simulated_speed = 60.0 + (random.uniform(-25.0, 45.0) if self.simulate_speed_variation else 0.0)

                    try:
                        frame = self._fetch_test_frame(self.total_frames)

                        # 1. Execute full perception & Hugging Face inference pipeline
                        dms_status = self.dms.process_frame(frame, speed_kph=simulated_speed)

                        # Verify contract invariants
                        assert isinstance(dms_status, dict), "DMS status is not a dictionary"
                        assert "drowsy" in dms_status, "Missing 'drowsy' in DMS status"
                        assert "huggingface" in dms_status, "Missing 'huggingface' telemetry"

                        # Track class distribution
                        hf = dms_status.get("huggingface") or {}
                        label = str(hf.get("label") or "UNKNOWN")
                        self.class_counts[label] = self.class_counts.get(label, 0) + 1

                        # 2. Run safety core telemetry assessment
                        signal = DriverBehaviorSignal(
                            driver_id=str(dms_status.get("driver_id", "drv_test")),
                            vehicle_id="veh_stress_test",
                            drowsiness_score=0.9 if dms_status.get("drowsy") else 0.1,
                            distraction_score=0.9 if dms_status.get("distracted") else 0.1,
                            yawning_score=0.85 if dms_status.get("yawning") else 0.1,
                            phone_usage_score=float(dms_status.get("phone_usage_score", 0.0)),
                            speed_kph=simulated_speed,
                            timestamp_ms=int(time.time() * 1000),
                            main_ai_model="Hugging Face",
                            hf_state=label,
                            hf_confidence=float(hf.get("score") or 0.0),
                        )
                        assessment = self.safety_monitor.evaluate(signal, now_ms=int(time.time() * 1000))
                        assert assessment.risk_level is not None, "Safety assessment returned None risk_level"

                        # 3. Verify JSON serialization round-trip (mimicking dashboard API)
                        json_payload = json.dumps({
                            "status": dms_status.get("drowsy"),
                            "risk": assessment.risk_level.value,
                            "hf": label,
                        })
                        assert len(json_payload) > 0

                        if delay_s > 0:
                            time.sleep(delay_s)

                    except Exception as exc:
                        cycle_errors += 1
                        self.total_errors += 1
                        stack = traceback.format_exc()
                        err_record = {
                            "frame": self.total_frames,
                            "cycle": cycle_idx,
                            "error": str(exc),
                            "traceback": stack,
                        }
                        self.error_log.append(err_record)
                        self.log(f"[CRASH/ERROR on Frame #{self.total_frames}]: {exc}\n{stack}")

                # Cycle Telemetry Report
                cycle_duration = time.time() - cycle_start_time
                cycle_fps = frames_per_cycle / max(cycle_duration, 0.001)
                current_mem_mb, peak_mem_mb = [m / (1024 * 1024) for m in tracemalloc.get_traced_memory()]

                self.log(
                    f"[CYCLE {cycle_idx:3d}{'' if not infinite else f'/{cycles}'}] "
                    f"Frames: {self.total_frames:5d} | "
                    f"Speed: {cycle_fps:5.1f} FPS | "
                    f"Mem: {current_mem_mb:5.1f}MB (Peak: {peak_mem_mb:5.1f}MB) | "
                    f"Cycle Errors: {cycle_errors} | Total Errors: {self.total_errors}"
                )

        except KeyboardInterrupt:
            self.log("[INTERRUPT] Test interrupted manually by user. Generating final report...")

        total_elapsed = time.time() - self.start_time
        avg_fps = self.total_frames / max(total_elapsed, 0.001)
        final_current, final_peak = [m / (1024 * 1024) for m in tracemalloc.get_traced_memory()]
        tracemalloc.stop()

        self.log(
            "\n"
            "========================================================\n"
            "   DRISHTI AI CONTINUOUS STABILITY TEST RESULTS\n"
            "========================================================\n"
            f"Total Frames Processed:    {self.total_frames}\n"
            f"Total Duration:            {total_elapsed:.2f} seconds\n"
            f"Average Processing Speed:  {avg_fps:.2f} FPS\n"
            f"Final Memory Allocated:    {final_current:.2f} MB\n"
            f"Peak Memory Allocated:     {final_peak:.2f} MB\n"
            f"Hugging Face Classes Seen: {self.class_counts}\n"
            f"Total Crashes / Errors:    {self.total_errors}\n"
            "========================================================"
        )

        if self.total_errors == 0:
            self.log("[PASS] STATUS: PERFECT HEALTH - Zero crashes or memory faults detected.")
            return True
        else:
            self.log(f"[FAIL] STATUS: FAILED with {self.total_errors} unhandled error(s).")
            return False


def main() -> int:
    parser = argparse.ArgumentParser(description="DRISHTI AI Continuous Stability & Stress Test")
    parser.add_argument("--cycles", type=int, default=10, help="Cycles to run (0 for infinite loop)")
    parser.add_argument("--frames-per-cycle", type=int, default=30, help="Frames per cycle batch")
    parser.add_argument("--delay", type=float, default=0.0, help="Artificial delay between frames (seconds)")
    parser.add_argument("--no-adversarial", action="store_true", help="Disable extreme/corrupted frames")
    parser.add_argument("--log-file", default="artifacts/continuous_stability_test.log", help="Log output path")
    parser.add_argument("--dataset-dir", default="dataset", help="Path to evaluation dataset")
    args = parser.parse_args()

    tester = ContinuousStabilityTester(
        dataset_dir=Path(args.dataset_dir),
        log_file=Path(args.log_file) if args.log_file else None,
        test_adversarial=not args.no_adversarial,
    )

    success = tester.run(
        cycles=args.cycles,
        frames_per_cycle=args.frames_per_cycle,
        delay_s=args.delay,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
