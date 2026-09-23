import os
import time
import unittest
from pathlib import Path

from ai_tracking.driver_monitor import EdgeAIClassifier, DrishtiAIDMS
from ai_tracking.huggingface_client import HuggingFaceDriverClassifier, HuggingFaceEmotionClassifier
from ai_tracking.safety_core import DriverBehaviorMonitor, DriverBehaviorSignal, DriverRiskLevel


class HuggingFaceDriverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_emotion = os.environ.get("DRISHTI_HF_EMOTION")
        self._previous_model = os.environ.get("DRISHTI_HF_MODEL")

    def tearDown(self) -> None:
        if self._previous_emotion is None:
            os.environ.pop("DRISHTI_HF_EMOTION", None)
        else:
            os.environ["DRISHTI_HF_EMOTION"] = self._previous_emotion

        if self._previous_model is None:
            os.environ.pop("DRISHTI_HF_MODEL", None)
        else:
            os.environ["DRISHTI_HF_MODEL"] = self._previous_model

    def test_disabled_classifier_skips_inference(self) -> None:
        os.environ["DRISHTI_HF_EMOTION"] = "0"
        classifier = HuggingFaceDriverClassifier()
        result = classifier.classify(frame=None, landmarks=[])
        self.assertFalse(classifier.enabled)
        self.assertEqual(result["label"], "DISABLED")
        self.assertEqual(result["backend"], "disabled")

    def test_local_pipeline_maps_happy_emotion(self) -> None:
        os.environ["DRISHTI_HF_EMOTION"] = "1"
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "happy", "score": 0.91}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["label"], "HAPPY")
        self.assertEqual(result["score"], 0.91)
        self.assertFalse(result["stress"])
        self.assertEqual(result["backend"], "transformers")

    def test_driver_state_drowsy_classification(self) -> None:
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "drowsy", "score": 0.88}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["label"], "DROWSY")
        self.assertTrue(result["drowsy"])
        self.assertFalse(result["alert_normal"])
        self.assertEqual(result["primary_model"], "Hugging Face")

    def test_driver_state_alert_normal_classification(self) -> None:
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "alert_normal", "score": 0.95}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["label"], "ALERT_NORMAL")
        self.assertTrue(result["alert_normal"])
        self.assertFalse(result["drowsy"])

    def test_driver_state_distracted_classification(self) -> None:
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "distracted", "score": 0.82}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertTrue(result["distracted"])

    def test_driver_state_phone_use_classification(self) -> None:
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "phone_use", "score": 0.90}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertTrue(result["phone_use"])

    def test_driver_state_yawning_classification(self) -> None:
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "yawning", "score": 0.79}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertTrue(result["yawning"])

    def test_throttle_returns_cached_result(self) -> None:
        classifier = HuggingFaceDriverClassifier()
        classifier._backend = "transformers"
        classifier.min_interval_s = 30
        classifier._last_run = time.monotonic()
        classifier._last_result = classifier._base_result("ALERT_NORMAL")
        classifier._last_result["score"] = 0.9
        classifier._classifier = lambda image, top_k=1: [{"label": "drowsy", "score": 0.99}]
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["label"], "ALERT_NORMAL")

    def test_edge_ai_includes_hf_label(self) -> None:
        result = EdgeAIClassifier().classify(hf_label="DROWSY", hf_score=0.85, drowsy=True)
        self.assertIn("hf_drowsy", result["reasons"])
        self.assertEqual(result["main_ai_model"], "Hugging Face")
        self.assertGreaterEqual(result["confidence"], 0.85)

    def test_safety_core_flags_hf_state(self) -> None:
        monitor = DriverBehaviorMonitor()
        signal = DriverBehaviorSignal(
            driver_id="drv_001",
            vehicle_id="veh_001",
            main_ai_model="Hugging Face",
            hf_state="DISTRACTED",
            hf_confidence=0.88,
            timestamp_ms=1000,
        )
        result = monitor.evaluate(signal, now_ms=1000)
        self.assertIn("hf_distracted", result.reasons)
        self.assertEqual(result.main_ai_model, "Hugging Face")

    def test_backward_compatibility_alias(self) -> None:
        self.assertIs(HuggingFaceEmotionClassifier, HuggingFaceDriverClassifier)


if __name__ == "__main__":
    unittest.main()
