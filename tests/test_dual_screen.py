"""Automated unit and integration test for DRISHTI AI Dual-Screen Showcase.

Uses standard Python unittest library.
Tests:
1. Truck Cockpit UI route (GET / and GET /cockpit)
2. Fleet Operations Control Room route (GET /control-room and GET /fleet)
3. Telematics API (GET /api/telemetry) with dynamic IP, QR URL, and dispatcher count
4. Drive-by-Wire speed API (POST /api/speed)
5. Remote Dispatcher Interventions (POST /api/remote_action)
6. Incident Audit Log (GET /api/audit_log)
"""

import json
import unittest
from app import app, remote_commands, incident_log, vehicle_speed_kph


class TestDualScreenShowcase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_cockpit_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("DRISHTI DMS", html)
        self.assertIn("BharatBenz", html)
        self.assertIn("PRIMARY INSTRUMENT CLUSTER", html)
        self.assertIn("CAN-BUS ENGINE TELEMETRY", html)
        self.assertIn("AIR RESERVOIR", html)

    def test_control_room_route(self):
        response = self.client.get("/control-room")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("DRISHTI FLEET COMMAND", html)
        self.assertIn("TRIGGER IN-CAB ALARM BUZZER", html)
        self.assertIn("FORCE JIOSPACEFIBER SATELLITE", html)
        self.assertIn("DISPATCH MANDATORY REST DIRECTIVE", html)

    def test_telemetry_api(self):
        response = self.client.get("/api/telemetry?client=dispatcher")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertIn("speed_kph", data)
        self.assertIn("local_ip", data)
        self.assertIn("control_room_url", data)
        self.assertIn("remote_commands", data)
        self.assertGreaterEqual(data["dispatchers_connected"], 1)
        self.assertIn("http://", data["control_room_url"])

    def test_drive_by_wire_speed(self):
        res1 = self.client.post("/api/speed", json={"speed": 75.0})
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.data.decode("utf-8"))
        self.assertEqual(data1["speed_kph"], 75.0)
        self.assertFalse(data1["overspeed"])

        res2 = self.client.post("/api/speed", json={"delta": 10.0})
        self.assertEqual(res2.status_code, 200)
        data2 = json.loads(res2.data.decode("utf-8"))
        self.assertEqual(data2["speed_kph"], 85.0)
        self.assertTrue(data2["overspeed"])

    def test_remote_dispatcher_buzzer(self):
        response = self.client.post("/api/remote_action", json={"action": "trigger_buzzer"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["action"], "trigger_buzzer")
        self.assertTrue(data["remote_commands"]["buzzer_active"])

        telem = json.loads(self.client.get("/api/telemetry").data.decode("utf-8"))
        self.assertTrue(telem["remote_commands"]["buzzer_active"])

    def test_remote_dispatcher_pull_over(self):
        msg = "MANDATORY REST DIRECTIVE: Pull over at KM 142 rest area."
        response = self.client.post("/api/remote_action", json={"action": "pull_over", "message": msg})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertTrue(data["remote_commands"]["pull_over"])
        self.assertEqual(data["remote_commands"]["pull_over_msg"], msg)

    def test_incident_audit_log(self):
        # Post an action to ensure at least one incident is recorded
        self.client.post("/api/remote_action", json={"action": "trigger_buzzer"})
        response = self.client.get("/api/audit_log")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertIn("events", data)
        self.assertGreater(len(data["events"]), 0)
        self.assertEqual(data["vehicle_id"], "DL-01-EA-4412")
        self.assertEqual(data["driver"], "Rohit Rajesh (ID: DRV-8821)")


if __name__ == "__main__":
    unittest.main()
