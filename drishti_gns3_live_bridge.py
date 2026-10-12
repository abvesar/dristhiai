"""DRISHTI AI <---> GNS3 Live Visual & Operational Synchronization Bridge

Synchronizes the live Drishti AI Dashboard (Flask :5050 / :5000) directly to GNS3:
1. Operational LEDs: Automatically stops the Jio-4G node (turning its canvas LED RED)
   when in a dead zone or during critical failover, and starts it (turning it GREEN)
   when cellular is online.
2. Real-Time Dynamic Node Labels: Updates node names directly on the GNS3 canvas:
   - Vehicle-DMS: [60kmh-OK] vs [⚠️CRITICAL-DROWSY] vs [⚠️DISTRACTED]
   - Vehicle-GW:  [4G-ACTIVE] vs [SAT-FAILOVER]
   - Jio-4G:      [ONLINE] vs [DEADZONE-OFFLINE]
   - JioSpaceFiber: [STANDBY] vs [FAILOVER-ACTIVE]
   - HQ-Gateway:  [4G-INGEST] vs [SAT-INGEST]
   - HQ-Server:   [NORMAL-60kmh] vs [CRITICAL-85kmh]
3. Live Telemetry HUD: Maintains a clean, single HUD drawing at (-380, -200).
"""

import base64
import configparser
import html
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request


def get_auth():
    appdata = os.environ.get("APPDATA", "")
    p = Path(appdata) / "GNS3" / "2.2" / "gns3_server.ini"
    cfg = configparser.ConfigParser()
    cfg.read(p)
    user = cfg.get("Server", "user")
    pwd = cfg.get("Server", "password")
    return "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()


class DrishtiGNS3LiveBridge:
    def __init__(self):
        self.auth = get_auth()
        self.headers = {"Authorization": self.auth, "Content-Type": "application/json"}
        self.pid = "04f0b1bb-b4ff-49dd-9099-aa7758c939e1"
        self.hud_drawing_id = None
        self.node_ids = {
            "server": None,
            "router": None,
            "cellular": None,
            "satellite": None,
            "veh_gw": None,
            "veh_dms": None,
        }
        self.cell_is_stopped = False
        self.last_state = ""
        self._cache_node_ids()

    def _cache_node_ids(self):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:3080/v2/projects/{self.pid}/nodes",
                headers={"Authorization": self.auth}
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                all_nodes = json.loads(resp.read().decode())
            for n in all_nodes:
                name = n["name"]
                nid = n["node_id"]
                if "HQ-Server" in name or "DrishtiAI" in name:
                    self.node_ids["server"] = nid
                elif "Gateway-RTR" in name or "HQ-Gateway" in name:
                    self.node_ids["router"] = nid
                elif "Cellular" in name or "Jio-4G" in name:
                    self.node_ids["cellular"] = nid
                    if n.get("status") == "stopped":
                        self.cell_is_stopped = True
                elif "SpaceFiber" in name or "MEO" in name:
                    self.node_ids["satellite"] = nid
                elif "Telematics-GW" in name or "Vehicle-GW" in name:
                    self.node_ids["veh_gw"] = nid
                elif "DMS" in name or "Vehicle-01" in name:
                    self.node_ids["veh_dms"] = nid
        except Exception as e:
            print(f"   [GNS3 WARN] Failed to cache node IDs: {e}")

    def _set_node_name(self, nid, name):
        if not nid:
            return
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:3080/v2/projects/{self.pid}/nodes/{nid}",
                data=json.dumps({"name": name}).encode(),
                headers=self.headers, method="PUT"
            )
            urllib.request.urlopen(req, timeout=2.0)
        except Exception:
            pass

    def _set_node_power(self, nid, start: bool):
        if not nid:
            return
        action = "start" if start else "stop"
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:3080/v2/projects/{self.pid}/nodes/{nid}/{action}",
                data=b"{}", headers=self.headers, method="POST"
            )
            urllib.request.urlopen(req, timeout=2.0)
        except Exception:
            pass

    def refresh_live_topology(self, link, risk, speed, drowsy, distracted, packet):
        """Pushes real-time telematics directly onto the GNS3 canvas via node states and labels."""
        is_satellite = ("Satellite" in link or "JioSpaceFiber" in link or drowsy or (speed >= 80 and distracted))

        # 1. Update Hardware Power LEDs & Uplink Names
        cell_id = self.node_ids.get("cellular")
        sat_id = self.node_ids.get("satellite")
        gw_id = self.node_ids.get("veh_gw")
        rtr_id = self.node_ids.get("router")
        dms_id = self.node_ids.get("veh_dms")
        srv_id = self.node_ids.get("server")

        if is_satellite:
            # Turn 4G tower LED RED (Link Down / Dead Zone)
            if not self.cell_is_stopped:
                self._set_node_power(cell_id, start=False)
                self.cell_is_stopped = True
            self._set_node_name(cell_id, "Jio-4G-[DEADZONE-OFFLINE]")
            self._set_node_name(sat_id, "JioSpaceFiber-[FAILOVER-ACTIVE]")
            self._set_node_name(gw_id, "Vehicle-GW-[SAT-FAILOVER]")
            self._set_node_name(rtr_id, "HQ-Gateway-[SAT-INGEST]")
        else:
            # Turn 4G tower LED GREEN (Link Online)
            if self.cell_is_stopped:
                self._set_node_power(cell_id, start=True)
                self.cell_is_stopped = False
            self._set_node_name(cell_id, "Jio-4G-[ONLINE]")
            self._set_node_name(sat_id, "JioSpaceFiber-[STANDBY]")
            self._set_node_name(gw_id, "Vehicle-GW-[4G-ACTIVE]")
            self._set_node_name(rtr_id, "HQ-Gateway-[4G-INGEST]")

        # 2. Update Vehicle DMS Node Label with live driver state
        spd_int = int(speed)
        if drowsy:
            dms_label = "Vehicle-DMS-[ALERT-DROWSY]"
        elif speed >= 80 and distracted:
            dms_label = "Vehicle-DMS-[ALERT-OVERSPEED]"
        elif distracted:
            dms_label = "Vehicle-DMS-[ALERT-DISTRACTED]"
        else:
            dms_label = f"Vehicle-DMS-[{spd_int}kmh-OK]"
        self._set_node_name(dms_id, dms_label)

        # 3. Update HQ Server Node Label
        risk_code = "CRIT" if (drowsy or (speed >= 80 and distracted)) else ("WARN" if distracted else "NORM")
        srv_label = f"HQ-Server-[{risk_code}-{spd_int}kmh]"
        self._set_node_name(srv_id, srv_label)

        # 4. Update HUD Drawing on canvas
        self._update_hud_drawing(link, risk, speed, drowsy, distracted, packet, is_satellite)

    refresh_hud = refresh_live_topology

    def _update_hud_drawing(self, link, risk, speed, drowsy, distracted, packet, is_satellite):
        if drowsy:
            border = "#ef4444"
            bg = "#450a0a"
            status = "CRITICAL: DROWSINESS DETECTED (EYES CLOSED > 1.5s)"
            route = "JioSpaceFiber Satellite (Priority Failover)"
            badge_col = "#38bdf8"
        elif speed >= 80 and distracted:
            border = "#ef4444"
            bg = "#450a0a"
            status = "HIGH RISK: OVERSPEED + DISTRACTION ESCALATION"
            route = "JioSpaceFiber Satellite (SES MEO)"
            badge_col = "#38bdf8"
        elif is_satellite:
            border = "#0284c7"
            bg = "#082f49"
            status = "DEAD ZONE: 4G/5G CELLULAR DROPOUT"
            route = "JioSpaceFiber Satellite (Active Uplink)"
            badge_col = "#38bdf8"
        elif distracted:
            border = "#f59e0b"
            bg = "#451a03"
            status = "WARNING: DISTRACTED DRIVING DETECTED"
            route = "Jio 4G/5G Cellular (Active)"
            badge_col = "#4ade80"
        else:
            border = "#22c55e"
            bg = "#052e16"
            status = "NORMAL: DRIVER ATTENTIVE & ATTENDING ROAD"
            route = "Jio 4G/5G Cellular (Primary Stream)"
            badge_col = "#4ade80"

        safe_status = html.escape(status)
        safe_route = html.escape(route)
        safe_packet = html.escape(str(packet))

        svg = f"""<svg height="54" width="700">
  <rect width="690" height="48" rx="8" fill="{bg}" stroke="{border}" stroke-width="2"/>
  <circle cx="20" cy="24" r="6" fill="{border}"/>
  <text x="36" y="22" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#ffffff">LIVE TELEMETRY: {safe_status}</text>
  <text x="36" y="38" font-family="Segoe UI, Arial" font-size="9" fill="#94a3b8">Active Route: <tspan fill="{badge_col}" font-weight="bold">{safe_route}</tspan> | Speed: <tspan fill="#ffffff" font-weight="bold">{int(speed)} km/h</tspan> | Packet: <tspan fill="#f1f5f9" font-family="monospace">{safe_packet}</tspan></text>
</svg>"""

        # Ensure single clean HUD drawing
        try:
            if not self.hud_drawing_id:
                # Find if any exists at (-380, -200)
                req = urllib.request.Request(
                    f"http://127.0.0.1:3080/v2/projects/{self.pid}/drawings",
                    headers={"Authorization": self.auth}
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    drawings = json.loads(resp.read().decode())
                for d in drawings:
                    if d.get("x") == -380 and d.get("y") == -200:
                        self.hud_drawing_id = d["drawing_id"]
                        break

            if self.hud_drawing_id:
                # Update existing drawing
                req_put = urllib.request.Request(
                    f"http://127.0.0.1:3080/v2/projects/{self.pid}/drawings/{self.hud_drawing_id}",
                    data=json.dumps({"svg": svg}).encode(),
                    headers=self.headers, method="PUT"
                )
                urllib.request.urlopen(req_put, timeout=2.0)
            else:
                # Create drawing
                req_post = urllib.request.Request(
                    f"http://127.0.0.1:3080/v2/projects/{self.pid}/drawings",
                    data=json.dumps({"x": -380, "y": -200, "z": 2, "svg": svg}).encode(),
                    headers=self.headers, method="POST"
                )
                with urllib.request.urlopen(req_post, timeout=2.0) as resp:
                    created = json.loads(resp.read().decode())
                    self.hud_drawing_id = created.get("drawing_id")
        except Exception:
            pass


def fetch_dashboard_telemetry():
    """Polls the Flask dashboard for live telematics."""
    port = os.environ.get("DRISHTI_PORT", "5050")
    for p in (port, "5000"):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{p}/api/telemetry")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            continue
    return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 72)
    print("      DRISHTI AI <---> GNS3 HARDWARE & TELEMETRY LIVE BRIDGE")
    print("=" * 72)
    print(" [*] Connecting to GNS3 project...")
    bridge = DrishtiGNS3LiveBridge()
    print(" [+] Hardware synchronization active (Cellular LED & Satellite handover)!")
    print(" [*] Monitoring Dashboard at http://localhost:5050/ (or :5000)...")

    last_state = ""

    try:
        while True:
            data = fetch_dashboard_telemetry()
            if data:
                link = data.get("network_link", "Jio 4G/5G Cellular")
                risk = data.get("risk_level", "NORMAL")
                speed = float(data.get("speed_kph", 60.0))
                drowsy = bool(data.get("drowsy", False))
                distracted = bool(data.get("distracted", False))
                packet = data.get("compact_packet", "DRST|V1|R:NOR|F:none")

                state = f"{link}-{risk}-{int(speed)}-{drowsy}-{distracted}"
                if state != last_state:
                    bridge.refresh_live_topology(link, risk, speed, drowsy, distracted, packet)
                    last_state = state
                    print(f"   [GNS3 SYNC] Route: {link:<30} | Speed: {int(speed)} km/h | Packet: {packet}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] Bridge stopped.")


if __name__ == "__main__":
    main()
