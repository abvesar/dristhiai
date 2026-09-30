"""Unit and Integration Tests for DRISHTI AI Phase 1 Security Layer.

Tests:
1. Satellite packet signing and verification
2. Tampered satellite packet rejection
3. Expired satellite packet (anti-replay) rejection
4. Cloud JSON telemetry signing and verification
5. Tampered cloud JSON payload rejection
6. Edge API token validation (X-Drishti-Fleet-Token, Bearer, query string)
7. Flask dispatch endpoints: unauthorized rejection (401) vs authorized access (200)
"""

from __future__ import annotations

import json
import time
import unittest

from ai_tracking.security import (
    DEFAULT_FLEET_API_KEY,
    DEFAULT_TELEMATICS_SECRET,
    EdgeApiSecurity,
    TelemetrySigner,
)
from app import app


class TestSecurityLayer(unittest.TestCase):
    def setUp(self):
        self.secret_key = b"test_secret_automotive_psk_99"
        self.api_key = "drishti-test-fleet-token-1234"

    def test_satellite_packet_signing_and_verification(self):
        payload = {
            "risk_level": "HIGH",
            "reasons": ["drowsiness_high", "eyes_closed_long"],
        }
        signed = TelemetrySigner.sign_satellite_packet(payload, secret_key=self.secret_key)
        self.assertTrue(signed.startswith("DRST|V1|T:"))
        self.assertIn("|R:HIG|F:drow|S:", signed)

        valid, msg, parsed = TelemetrySigner.verify_satellite_packet(signed, secret_key=self.secret_key)
        self.assertTrue(valid, msg)
        self.assertEqual(parsed.get("R"), "HIG")
        self.assertEqual(parsed.get("F"), "drow")

    def test_satellite_packet_tamper_detection(self):
        payload = {"risk_level": "HIGH", "reasons": ["drowsiness_high"]}
        signed = TelemetrySigner.sign_satellite_packet(payload, secret_key=self.secret_key)

        # Attacker tampers risk from HIG to NOR without updating signature
        tampered = signed.replace("|R:HIG|", "|R:NOR|")
        valid, msg, _ = TelemetrySigner.verify_satellite_packet(tampered, secret_key=self.secret_key)
        self.assertFalse(valid)
        self.assertIn("mismatch", msg.lower())

    def test_satellite_packet_anti_replay_expired(self):
        payload = {"risk_level": "HIGH", "reasons": ["drowsiness_high"]}
        # Simulate an old captured packet from 500 seconds ago
        old_epoch = int(time.time()) - 500
        signed_old = TelemetrySigner.sign_satellite_packet(
            payload, secret_key=self.secret_key, timestamp=old_epoch
        )

        valid, msg, _ = TelemetrySigner.verify_satellite_packet(
            signed_old, secret_key=self.secret_key, max_skew_sec=60
        )
        self.assertFalse(valid)
        self.assertIn("skew", msg.lower())

    def test_cloud_payload_signing_and_verification(self):
        payload = {
            "driver_id": "DRV_8821",
            "vehicle_id": "DL-01-EA-4412",
            "risk_level": "HIGH",
            "speed_kph": 88.5,
            "reasons": ["drowsiness_high"],
        }
        signed = TelemetrySigner.sign_cloud_payload(payload, secret_key=self.secret_key)
        self.assertIn("_auth", signed)
        self.assertEqual(signed["_auth"]["version"], "1.0")

        valid, msg = TelemetrySigner.verify_cloud_payload(signed, secret_key=self.secret_key)
        self.assertTrue(valid, msg)

    def test_cloud_payload_tamper_detection(self):
        payload = {"driver_id": "DRV_8821", "speed_kph": 90.0, "risk_level": "HIGH"}
        signed = TelemetrySigner.sign_cloud_payload(payload, secret_key=self.secret_key)

        # Attacker tampers speed or risk level in transit
        signed["speed_kph"] = 40.0
        valid, msg = TelemetrySigner.verify_cloud_payload(signed, secret_key=self.secret_key)
        self.assertFalse(valid)
        self.assertIn("failed", msg.lower())

    def test_edge_api_security_tokens(self):
        valid_token = EdgeApiSecurity.get_active_token()
        self.assertTrue(EdgeApiSecurity.is_valid_token(valid_token))
        self.assertFalse(EdgeApiSecurity.is_valid_token("invalid_attacker_token"))
        self.assertFalse(EdgeApiSecurity.is_valid_token(""))
        self.assertFalse(EdgeApiSecurity.is_valid_token(None))

    def test_flask_endpoint_security_enforcement(self):
        app.config["TESTING"] = True
        app.config["DRISHTI_ENFORCE_AUTH"] = True
        client = app.test_client()

        # 1. POST /api/remote_action without token -> 401 Unauthorized
        res_unauth = client.post("/api/remote_action", json={"action": "trigger_buzzer"})
        self.assertEqual(res_unauth.status_code, 401)
        data = json.loads(res_unauth.data.decode("utf-8"))
        self.assertEqual(data["status"], "error")

        # 2. POST /api/remote_action with invalid token -> 401 Unauthorized
        res_bad = client.post(
            "/api/remote_action",
            json={"action": "trigger_buzzer"},
            headers={"X-Drishti-Fleet-Token": "bad_token_999"},
        )
        self.assertEqual(res_bad.status_code, 401)

        # 3. POST /api/remote_action with valid X-Drishti-Fleet-Token -> 200 OK
        valid_token = EdgeApiSecurity.get_active_token()
        res_ok = client.post(
            "/api/remote_action",
            json={"action": "trigger_buzzer"},
            headers={"X-Drishti-Fleet-Token": valid_token},
        )
        self.assertEqual(res_ok.status_code, 200)

        # 4. POST /api/remote_action with valid Authorization: Bearer <token> -> 200 OK
        res_bearer = client.post(
            "/api/remote_action",
            json={"action": "trigger_buzzer"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        self.assertEqual(res_bearer.status_code, 200)

        # 5. GET /api/audit_log without token -> 401 Unauthorized
        res_audit_unauth = client.get("/api/audit_log")
        self.assertEqual(res_audit_unauth.status_code, 401)

        # 6. GET /api/audit_log with token -> 200 OK
        res_audit_ok = client.get(
            "/api/audit_log",
            headers={"X-Drishti-Fleet-Token": valid_token},
        )
        self.assertEqual(res_audit_ok.status_code, 200)

        # Reset flag
        app.config["DRISHTI_ENFORCE_AUTH"] = False


if __name__ == "__main__":
    unittest.main()
