"""Hugging Face Driver Behavior & Facial Analysis Client for DRISHTI AI.

Acts as the primary AI inference engine for driver state classification
(alert_normal, drowsy, distracted, yawning, phone_use) and facial expression / stress analysis.
Prioritizes the local fine-tuned Hugging Face transformer model
('models/drishti_driver_classifier') with transparent fallback to Hugging Face Hub / Inference API.
"""

from __future__ import annotations

import os
from pathlib import Path
import threading
import time
from typing import Dict, Optional

import cv2
import numpy as np


class HuggingFaceDriverClassifier:
    """Primary Hugging Face image classification engine for driver monitoring."""

    DEFAULT_HUB_MODEL = "trpakov/vit-face-expression"
    LOCAL_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "drishti_driver_classifier"
    STRESS_LABELS = {
        "ANGRY", "DISGUST", "FEAR", "SAD",
        "DROWSY", "DISTRACTED", "YAWNING", "PHONE_USE",
    }
    DRIVER_STATE_LABELS = {
        "ALERT_NORMAL", "DROWSY", "DISTRACTED", "YAWNING", "PHONE_USE",
    }

    def __init__(self) -> None:
        raw_enabled = os.environ.get("DRISHTI_HF_EMOTION", "1").strip().lower()
        self.enabled = raw_enabled not in {"0", "false", "no", "off"}

        # Prioritize explicitly configured model, then local fine-tuned model, then hub default
        if "DRISHTI_HF_MODEL" in os.environ and os.environ["DRISHTI_HF_MODEL"].strip():
            self.model_id = os.environ["DRISHTI_HF_MODEL"].strip()
        elif (self.LOCAL_MODEL_PATH / "config.json").is_file():
            self.model_id = str(self.LOCAL_MODEL_PATH)
        else:
            self.model_id = self.DEFAULT_HUB_MODEL

        self.min_interval_s = float(os.environ.get("DRISHTI_HF_INTERVAL", "1.0"))
        self._token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN") or None
        self._classifier = None
        self._inference_client = None
        self._backend = ""
        self._load_error = ""
        self._loading = False
        self._load_lock = threading.Lock()
        self._last_run = 0.0
        self._last_result: Dict[str, object] = self._base_result("PENDING" if self.enabled else "DISABLED")
        self._predicting = False
        if self.enabled:
            self._ensure_loaded_async()

    @property
    def is_local_driver_model(self) -> bool:
        norm = self.model_id.replace("\\", "/").rstrip("/")
        return norm.endswith("models/drishti_driver_classifier") or "drishti_driver_classifier" in norm

    def idle_status(self) -> Dict[str, object]:
        if not self.enabled:
            return self._base_result("DISABLED")
        if self._load_error:
            return self._base_result("UNAVAILABLE")
        if self._last_result.get("label") not in {"DISABLED", "UNAVAILABLE", "PENDING", "NO FACE"}:
            return dict(self._last_result)
        return self._base_result("NO FACE")

    def classify(self, frame, landmarks) -> Dict[str, object]:
        if not self.enabled:
            return self._base_result("DISABLED")

        now = time.monotonic()
        if self._backend and (now - self._last_run) < self.min_interval_s:
            return dict(self._last_result)

        self._ensure_loaded_async()
        if self._classifier is None and self._inference_client is None:
            label = "UNAVAILABLE" if self._load_error else "PENDING"
            result = self._base_result(label)
            self._last_result = result
            return result

        face_image = self._crop_face(frame, landmarks)
        if face_image is None:
            return self.idle_status() if self._last_result.get("label") not in {"PENDING"} else self._base_result("NO FACE")

        # Synchronous execution when min_interval_s <= 0 (e.g. unit tests)
        if self.min_interval_s <= 0:
            return self._execute_predict(face_image, now)

        # Asynchronous execution for real-time video streaming (zero FPS drop)
        if not self._predicting:
            self._predicting = True
            self._last_run = now
            threading.Thread(
                target=self._async_predict_worker,
                args=(face_image, now),
                name="drishti-hf-predict",
                daemon=True,
            ).start()

        return dict(self._last_result)

    def _execute_predict(self, face_image, now: float) -> Dict[str, object]:
        try:
            prediction = self._predict(face_image)
            raw_label = str(prediction.get("label") or "UNKNOWN").strip()
            label = raw_label.upper()
            score = round(float(prediction.get("score") or 0.0), 3)

            result = self._base_result(label)
            result["score"] = score
            result["drowsy"] = (label in {"DROWSY", "SLEEPY"}) and (score >= 0.45)
            result["distracted"] = (label in {"DISTRACTED", "LOOKING_AWAY"}) and (score >= 0.45)
            result["yawning"] = (label == "YAWNING") and (score >= 0.45)
            result["phone_use"] = (label in {"PHONE_USE", "PHONE_USAGE"}) and (score >= 0.45)
            result["alert_normal"] = (label in {"ALERT_NORMAL", "ALERT", "NORMAL"}) and (score >= 0.50)
            result["stress"] = (label in self.STRESS_LABELS) and (score >= 0.55)

            self._last_run = now
            self._last_result = result
            return result
        except Exception as exc:
            self._load_error = str(exc)
            result = self._base_result("UNAVAILABLE")
            self._last_result = result
            return result

    def _async_predict_worker(self, face_image, now: float) -> None:
        try:
            self._execute_predict(face_image, now)
        finally:
            self._predicting = False

    def _ensure_loaded_async(self) -> None:
        if self._classifier is not None or self._inference_client is not None or self._load_error or not self.enabled:
            return
        with self._load_lock:
            if self._loading or self._classifier is not None or self._inference_client is not None or self._load_error:
                return
            self._loading = True
            threading.Thread(target=self._load, name="drishti-hf-load", daemon=True).start()

    def _load(self) -> None:
        local_error = ""
        try:
            from transformers import pipeline

            device = self._local_device()
            print(f"[DRISHTI] Loading primary Hugging Face model {self.model_id} (transformers, device={device})")
            self._classifier = pipeline(
                "image-classification",
                model=self.model_id,
                device=device,
            )
            self._backend = "transformers"
            return
        except Exception as exc:
            local_error = str(exc)

        try:
            from huggingface_hub import InferenceClient

            print(f"[DRISHTI] Using Hugging Face Inference API fallback for {self.model_id}")
            self._inference_client = InferenceClient(model=self.model_id, token=self._token)
            self._backend = "inference_api"
            return
        except Exception as exc:
            self._load_error = f"transformers: {local_error}; inference_api: {exc}"
        finally:
            self._loading = False

    def _predict(self, face_image) -> Dict[str, object]:
        if self._classifier is not None:
            raw = self._classifier(face_image, top_k=1)
            return self._top_prediction(raw)
        raw = self._inference_client.image_classification(face_image, top_k=1)
        return self._top_prediction(raw)

    @staticmethod
    def _top_prediction(raw) -> Dict[str, object]:
        item = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
        if isinstance(item, dict):
            return {"label": item.get("label", ""), "score": item.get("score") or 0.0}
        return {
            "label": getattr(item, "label", ""),
            "score": getattr(item, "score", 0.0) or 0.0,
        }

    @staticmethod
    def _local_device() -> int:
        try:
            import torch

            return 0 if torch.cuda.is_available() else -1
        except Exception:
            return -1

    @staticmethod
    def _crop_face(frame, landmarks) -> Optional[object]:
        height, width = frame.shape[:2]
        points = np.array([(point.x * width, point.y * height) for point in landmarks], dtype=np.float32)
        x_min, y_min = np.maximum(np.min(points, axis=0).astype(int) - 24, 0)
        x_max, y_max = np.minimum(np.max(points, axis=0).astype(int) + 24, [width, height])
        if x_max <= x_min or y_max <= y_min:
            return None
        try:
            from PIL import Image

            crop = cv2.cvtColor(frame[y_min:y_max, x_min:x_max], cv2.COLOR_BGR2RGB)
            return Image.fromarray(crop)
        except Exception:
            return None

    def _base_result(self, label: str) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "primary_model": "Hugging Face",
            "backend": self._backend or ("disabled" if not self.enabled else "pending"),
            "label": label,
            "emotion": label,  # backward compatibility alias
            "score": 0.0,
            "model": self.model_id if self.enabled else "",
            "drowsy": False,
            "distracted": False,
            "yawning": False,
            "phone_use": False,
            "alert_normal": False,
            "stress": False,
            "error": self._load_error,
        }


# Maintain backward-compatible alias for existing imports
HuggingFaceEmotionClassifier = HuggingFaceDriverClassifier
