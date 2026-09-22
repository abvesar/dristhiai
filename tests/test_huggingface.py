import os
import time
import unittest

from ai_tracking.driver_monitor import EdgeAIClassifier
from ai_tracking.huggingface_client import HuggingFaceEmotionClassifier
from ai_tracking.safety_core import DriverBehaviorMonitor, DriverBehaviorSignal, DriverRiskLevel


class HuggingFaceEmotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous = os.environ.get("DRISHTI_HF_EMOTION")

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop("DRISHTI_HF_EMOTION", None)
        else:
            os.environ["DRISHTI_HF_EMOTION"] = self._previous

    def test_disabled_classifier_skips_inference(self) -> None:
        os.environ["DRISHTI_HF_EMOTION"] = "0"
        classifier = HuggingFaceEmotionClassifier()
        result = classifier.classify(frame=None, landmarks=[])
        self.assertFalse(classifier.enabled)
        self.assertEqual(result["emotion"], "DISABLED")
        self.assertEqual(result["backend"], "disabled")

    def test_local_pipeline_maps_happy_emotion(self) -> None:
        os.environ["DRISHTI_HF_EMOTION"] = "1"
        classifier = HuggingFaceEmotionClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "happy", "score": 0.91}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["emotion"], "HAPPY")
        self.assertEqual(result["score"], 0.91)
        self.assertFalse(result["stress"])
        self.assertEqual(result["backend"], "transformers")

    def test_sad_emotion_flags_stress(self) -> None:
        os.environ["DRISHTI_HF_EMOTION"] = "1"
        classifier = HuggingFaceEmotionClassifier()
        classifier._backend = "transformers"
        classifier._classifier = lambda image, top_k=1: [{"label": "sad", "score": 0.82}]
        classifier.min_interval_s = 0
        classifier._crop_face = staticmethod(lambda frame, landmarks: "face")
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["emotion"], "SAD")
        self.assertTrue(result["stress"])

    def test_throttle_returns_cached_result(self) -> None:
        os.environ["DRISHTI_HF_EMOTION"] = "1"
        classifier = HuggingFaceEmotionClassifier()
        classifier._backend = "transformers"
        classifier.min_interval_s = 30
        classifier._last_run = time.monotonic()
        classifier._last_result = classifier._base_result("HAPPY")
        classifier._last_result["score"] = 0.9
        classifier._classifier = lambda image, top_k=1: [{"label": "sad", "score": 0.99}]
        result = classifier.classify(frame=None, landmarks=[])
        self.assertEqual(result["emotion"], "HAPPY")

    def test_edge_ai_includes_emotional_stress(self) -> None:
        result = EdgeAIClassifier().classify(emotional_stress=True)
        self.assertIn("emotional_stress", result["reasons"])
        self.assertGreaterEqual(result["risk_score"], 0.1)

    def test_safety_core_flags_emotional_stress(self) -> None:
        monitor = DriverBehaviorMonitor()
        signal = DriverBehaviorSignal(
            driver_id="drv_001",
            vehicle_id="veh_001",
            emotional_stress_score=0.8,
            timestamp_ms=1000,
        )
        result = monitor.evaluate(signal, now_ms=1000)
        self.assertIn("emotional_stress", result.reasons)
        self.assertEqual(result.risk_level, DriverRiskLevel.NORMAL)


if __name__ == "__main__":
    unittest.main()
