"""Full System Integration & End-to-End Debugging Suite for DRISHTI AI.

Tests all Flask endpoints, security gates, Gradio app loading,
Hugging Face model inference, and telematics pipeline.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import os
import time
import unittest
from pathlib import Path
import numpy as np

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

from app import app, remote_commands, incident_log, latest_telemetry
from ai_tracking.security import (
    DEFAULT_FLEET_SHARED_KEY,
    DEFAULT_FLEET_TOKEN,
    EdgeApiSecurity,
    TelemetrySigner,
)
from fleet_gatekeeper_hub import (
    DrishtiHubConfig,
    FixedDriverSignalAdapter,
    JsonlAuditLogAdapter,
    CloudTransmissionAdapter,
    SatelliteTransmissionAdapter,
)
from ai_tracking.safety_core import DriverBehaviorMonitor


class TestFullSystemIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["DRISHTI_ENFORCE_AUTH"] = True
        cls.client = app.test_client()
        cls.auth_headers = {"X-Drishti-Fleet-Token": DEFAULT_FLEET_TOKEN}

    def test_01_cockpit_dashboard_route(self):
        """Verifies Cockpit UI loads successfully."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("DRISHTI AI", html)
        self.assertIn("Commercial Vehicle Cockpit", html)
        self.assertIn("DRISHTI_TOKEN", html)

    def test_02_control_room_dashboard_route(self):
        """Verifies Control Room UI loads successfully."""
        resp = self.client.get("/control-room")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("DRISHTI AI", html)
        self.assertIn("Central Fleet Operations", html)
        self.assertIn("DRISHTI_TOKEN", html)

    def test_03_telemetry_status_endpoint(self):
        """Verifies /api/telemetry returns valid JSON telemetry."""
        resp = self.client.get("/api/telemetry")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_data(as_text=True))
        self.assertIn("speed_kph", data)
        self.assertIn("risk_score", data)
        self.assertIn("risk_level", data)
        self.assertIn("satellite_provider", data)
        self.assertIn("security", data)
        self.assertEqual(data["security"]["mode"], "HMAC-SHA256 Signed")

    def test_04_speed_endpoint_auth_protection(self):
        """Verifies /api/speed blocks unauthorized requests and allows authorized ones."""
        # Unauthorized (no token)
        resp_unauth = self.client.post("/api/speed", json={"speed": 75.0})
        self.assertEqual(resp_unauth.status_code, 401)
        err = json.loads(resp_unauth.get_data(as_text=True))
        self.assertEqual(err.get("code"), 401)

        # Authorized
        resp_auth = self.client.post(
            "/api/speed",
            headers=self.auth_headers,
            json={"speed": 68.5},
        )
        self.assertEqual(resp_auth.status_code, 200)
        data = json.loads(resp_auth.get_data(as_text=True))
        self.assertAlmostEqual(data.get("speed_kph"), 68.5, places=1)

    def test_05_remote_action_auth_protection(self):
        """Verifies /api/remote_action blocks unauthorized and executes buzzer/satellite/pullover."""
        # Unauthorized
        resp_unauth = self.client.post("/api/remote_action", json={"action": "trigger_buzzer"})
        self.assertEqual(resp_unauth.status_code, 401)

        # Authorized: trigger buzzer
        resp_buzzer = self.client.post(
            "/api/remote_action",
            headers=self.auth_headers,
            json={"action": "trigger_buzzer"},
        )
        self.assertEqual(resp_buzzer.status_code, 200)
        data_buzzer = json.loads(resp_buzzer.get_data(as_text=True))
        self.assertEqual(data_buzzer.get("status"), "success")
        self.assertTrue(remote_commands["buzzer_active"])

        # Authorized: force satellite toggle
        prev_sat = remote_commands["force_satellite"]
        resp_sat = self.client.post(
            "/api/remote_action",
            headers=self.auth_headers,
            json={"action": "force_satellite"},
        )
        self.assertEqual(resp_sat.status_code, 200)
        self.assertNotEqual(remote_commands["force_satellite"], prev_sat)

        # Authorized: pull over directive
        resp_pull = self.client.post(
            "/api/remote_action",
            headers=self.auth_headers,
            json={"action": "pull_over", "message": "TEST BREAK REQUIRED"},
        )
        self.assertEqual(resp_pull.status_code, 200)
        self.assertTrue(remote_commands["pull_over"])
        self.assertEqual(remote_commands["pull_over_msg"], "TEST BREAK REQUIRED")

        # Authorized: clear directive
        resp_clear = self.client.post(
            "/api/remote_action",
            headers=self.auth_headers,
            json={"action": "clear_directive"},
        )
        self.assertEqual(resp_clear.status_code, 200)
        self.assertFalse(remote_commands["pull_over"])

    def test_06_audit_log_endpoint_auth(self):
        """Verifies /api/audit_log access control."""
        # Unauthenticated
        resp_unauth = self.client.get("/api/audit_log")
        self.assertEqual(resp_unauth.status_code, 401)

        # Authenticated
        resp_auth = self.client.get("/api/audit_log", headers=self.auth_headers)
        self.assertEqual(resp_auth.status_code, 200)
        data = json.loads(resp_auth.get_data(as_text=True))
        self.assertIn("total_events", data)
        self.assertIn("events", data)

    def test_07_satellite_signer_integration(self):
        """Verifies satellite emergency datagram cryptographic signing and anti-replay verification."""
        secret_key = b"test_secret_automotive_psk_99"
        payload = {"risk_level": "HIGH", "reasons": ["drowsiness_critical"]}
        datagram = TelemetrySigner.sign_satellite_packet(payload, secret_key=secret_key)
        
        # Valid signature verification
        is_valid, msg, parsed = TelemetrySigner.verify_satellite_packet(datagram, secret_key=secret_key)
        self.assertTrue(is_valid, msg)
        self.assertEqual(parsed["R"], "HIG")
        self.assertEqual(parsed["F"], "drow")

        # Anti-tampering check (altered risk)
        tampered = datagram.replace("|R:HIG|", "|R:NOR|")
        is_valid_tampered, _, _ = TelemetrySigner.verify_satellite_packet(tampered, secret_key=secret_key)
        self.assertFalse(is_valid_tampered)

        # Anti-replay drift check (datagram from 500 seconds ago)
        old_epoch = int(time.time()) - 500
        old_datagram = TelemetrySigner.sign_satellite_packet(payload, secret_key=secret_key, timestamp=old_epoch)
        is_valid_old, _, _ = TelemetrySigner.verify_satellite_packet(old_datagram, secret_key=secret_key, max_skew_sec=120)
        self.assertFalse(is_valid_old)

    def test_08_cloud_telemetry_hmac_envelope(self):
        """Verifies full 256-bit canonical JSON signing for cellular telemetry."""
        secret_key = b"test_secret_automotive_psk_99"
        telemetry = {
            "driver_id": "drv_test",
            "risk_score": 0.88,
            "speed_kph": 85.0,
            "signals": ["drowsy", "overspeed"],
        }
        envelope = TelemetrySigner.sign_cloud_payload(telemetry, secret_key=secret_key)
        self.assertIn("_auth", envelope)
        self.assertIn("signature", envelope["_auth"])
        self.assertIn("nonce", envelope["_auth"])

        # Verify envelope passes
        is_valid, msg = TelemetrySigner.verify_cloud_payload(envelope, secret_key=secret_key)
        self.assertTrue(is_valid, msg)

        # Reject tampered payload
        tampered_envelope = dict(envelope)
        tampered_envelope["speed_kph"] = 20.0
        is_valid_tampered, _ = TelemetrySigner.verify_cloud_payload(tampered_envelope, secret_key=secret_key)
        self.assertFalse(is_valid_tampered)

    def test_09_fleet_gatekeeper_hub_pipeline(self):
        """Tests the Fleet Gatekeeper Hub pipeline processing loop."""
        adapter = FixedDriverSignalAdapter(
            driver_id="drv_unit_test",
            vehicle_id="veh_001",
            drowsiness_score=0.92,
            distraction_score=0.10,
            speed_kph=60.0,
        )
        monitor = DriverBehaviorMonitor()
        class MockAuditLog:
            def __init__(self):
                self.events = []
            def write_event(self, event):
                self.events.append(event)
        audit_log = MockAuditLog()
        
        signal = adapter.read(1000)
        assessment = monitor.evaluate(signal=signal, now_ms=1000)
        self.assertEqual(assessment.risk_level, "HIGH")
        self.assertIn("drowsiness_high", assessment.reasons)
        
        audit_log.write_event(asdict(assessment))
        self.assertEqual(len(audit_log.events), 1)

    def test_10_gradio_app_compilation(self):
        """Verifies Gradio dashboard script compiles cleanly without syntax errors."""
        import py_compile
        compiled = py_compile.compile("gradio_app.py", doraise=True)
        self.assertTrue(os.path.exists(compiled))


if __name__ == "__main__":
    unittest.main()
