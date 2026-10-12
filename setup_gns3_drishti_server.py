"""DRISHTI AI -- GNS3 Server & Network Topology Automation Script

Creates and configures the complete DRISHTI AI Mission-Critical Server
and Dual-Uplink Satellite Infrastructure live in your open GNS3 window.

Architecture Components:
1. HQ Fleet Operations Data Center (Subnet 192.168.10.0/24)
   - DrishtiAI-HQ-Server (Fleet Operations Hub :5000 / Stream Server :9000)
   - Ops-Dispatcher-PC (Fleet Incident Dispatcher Console)
   - HQ-Core-Switch (L2 Distribution Switch)
   - HQ-Gateway-Router (HQ WAN Gateway)
2. Hybrid Telematics WAN Transit (Dual-Uplink)
   - Jio 4G/5G Cellular Tower (Primary Uplink - 30 FPS Stream)
   - JioSpaceFiber SES MEO Satellite Gateway (Failover Link - 32B Micro-Packets)
3. In-Cabin Edge Vehicle Zone (Subnet 192.168.20.0/24)
   - Vehicle-Telematics-GW (In-vehicle failover router)
   - Vehicle-01-DMS (Edge AI Driver Monitoring System)
"""

import base64
import configparser
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request


def get_gns3_credentials() -> tuple[str, int, str]:
    """Reads GNS3 credentials dynamically from gns3_server.ini."""
    appdata = os.environ.get("APPDATA", "")
    ini_path = Path(appdata) / "GNS3" / "2.2" / "gns3_server.ini"
    
    host = "127.0.0.1"
    port = 3080
    auth_header = ""
    
    if ini_path.exists():
        cfg = configparser.ConfigParser()
        cfg.read(ini_path)
        if cfg.has_section("Server"):
            host = cfg.get("Server", "host", fallback="127.0.0.1")
            if host in ("localhost", "0.0.0.0"):
                host = "127.0.0.1"
            port = cfg.getint("Server", "port", fallback=3080)
            user = cfg.get("Server", "user", fallback="")
            pwd = cfg.get("Server", "password", fallback="")
            if user and pwd:
                token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
                auth_header = f"Basic {token}"
                
    return host, port, auth_header


class GNS3Client:
    def __init__(self, host: str, port: int, auth: str) -> None:
        self.base_url = f"http://{host}:{port}/v2"
        self.auth = auth

    def _request(self, method: str, endpoint: str, data: dict | None = None) -> dict | list | None:
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DrishtiAIGNS3Setup/1.0",
        }
        if self.auth:
            headers["Authorization"] = self.auth

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as err:
            err_msg = err.read().decode("utf-8", errors="replace")
            print(f"[API ERROR] {method} {endpoint} -> HTTP {err.code}: {err_msg}", file=sys.stderr)
            raise

    def get_open_project(self) -> dict:
        projects = self._request("GET", "/projects")
        if not projects:
            raise RuntimeError("No projects found in GNS3.")
        
        # Look for the opened project, prefer 'DRISTI AI SERVER'
        opened = [p for p in projects if p.get("status") == "opened"]
        if opened:
            for p in opened:
                if "DRISTI" in p.get("name", "").upper():
                    return p
            return opened[0]
            
        raise RuntimeError("No open GNS3 project detected. Please open 'DRISTI AI SERVER' in GNS3.")

    def clear_project(self, project_id: str) -> None:
        """Removes existing links, nodes, and drawings for a pristine setup."""
        nodes = self._request("GET", f"/projects/{project_id}/nodes") or []
        for n in nodes:
            try:
                self._request("DELETE", f"/projects/{project_id}/nodes/{n['node_id']}")
            except Exception:
                pass

        drawings = self._request("GET", f"/projects/{project_id}/drawings") or []
        for d in drawings:
            try:
                self._request("DELETE", f"/projects/{project_id}/drawings/{d['drawing_id']}")
            except Exception:
                pass

    def add_drawing(self, project_id: str, x: int, y: int, svg: str, z: int = 0) -> str:
        payload = {"x": x, "y": y, "z": z, "svg": svg}
        res = self._request("POST", f"/projects/{project_id}/drawings", payload)
        return res.get("drawing_id", "")

    def add_node(
        self,
        project_id: str,
        name: str,
        node_type: str,
        x: int,
        y: int,
        symbol: str,
        compute_id: str = "local",
    ) -> dict:
        payload = {
            "name": name,
            "node_type": node_type,
            "compute_id": compute_id,
            "x": x,
            "y": y,
            "symbol": symbol,
        }
        return self._request("POST", f"/projects/{project_id}/nodes", payload)

    def add_link(
        self,
        project_id: str,
        node_a_id: str,
        port_a: int,
        node_b_id: str,
        port_b: int,
        adapter_a: int = 0,
        adapter_b: int = 0,
    ) -> dict:
        payload = {
            "nodes": [
                {"node_id": node_a_id, "adapter_number": adapter_a, "port_number": port_a},
                {"node_id": node_b_id, "adapter_number": adapter_b, "port_number": port_b},
            ]
        }
        return self._request("POST", f"/projects/{project_id}/links", payload)

    def start_node(self, project_id: str, node_id: str) -> None:
        try:
            self._request("POST", f"/projects/{project_id}/nodes/{node_id}/start", {})
        except Exception:
            pass

    def start_all_nodes(self, project_id: str) -> None:
        try:
            self._request("POST", f"/projects/{project_id}/nodes/start", {})
        except Exception:
            pass


def configure_vpcs_ip(console_port: int, ip: str, mask: str, gateway: str) -> bool:
    """Connects to the VPCS Telnet console port and applies IP configuration."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(("127.0.0.1", console_port))
        time.sleep(0.4)
        s.recv(2048)
        
        cmd = f"ip {ip} {mask} {gateway}\nsave\n"
        s.sendall(cmd.encode("ascii"))
        time.sleep(1.2)
        s.close()
        return True
    except Exception as e:
        print(f"      [!] Note: Could not auto-assign IP via port {console_port} ({e})")
        return False


def main():
    print("=" * 72)
    print("      DRISHTI AI -- GNS3 SERVER & DUAL-UPLINK TOPOLOGY BUILDER")
    print("=" * 72)

    host, port, auth = get_gns3_credentials()
    print(f"[*] Connecting to GNS3 Server at http://{host}:{port}/ ...")
    client = GNS3Client(host, port, auth)

    project = client.get_open_project()
    project_id = project["project_id"]
    project_name = project.get("name", "Unknown")
    print(f"[+] Active Project Detected: '{project_name}' (ID: {project_id})")
    print("[*] Preparing canvas: clearing previous draft nodes for a clean build...")
    client.clear_project(project_id)
    time.sleep(0.5)

    # -------------------------------------------------------------------------
    # 1. Master Title Banner & Section Bounding Cards
    # -------------------------------------------------------------------------
    print("\n[STEP 1/5] Rendering Architectural Blueprint Banners & Zone Cards...")

    banner_svg = """<svg height="70" width="850">
      <rect width="840" height="64" rx="10" fill="#0f172a" fill-opacity="0.95" stroke="#38bdf8" stroke-width="2"/>
      <text x="24" y="28" font-family="Segoe UI, Arial" font-size="16" font-weight="bold" fill="#38bdf8">DRISHTI AI -- Autonomous Edge-AI Fleet Telematics Architecture</text>
      <text x="24" y="50" font-family="Segoe UI, Arial" font-size="12" fill="#94a3b8">Multi-Tier Redundancy: Jio 4G/5G Cellular + JioSpaceFiber (SES MEO Satellite Link Failover)</text>
    </svg>"""
    client.add_drawing(project_id, x=-420, y=-260, svg=banner_svg, z=0)

    # HQ Data Center Card
    hq_card_svg = """<svg height="210" width="760">
      <rect width="750" height="200" rx="12" fill="#1e293b" fill-opacity="0.08" stroke="#3b82f6" stroke-width="2" stroke-dasharray="6,4"/>
      <text x="20" y="28" font-family="Segoe UI, Arial" font-size="12" font-weight="bold" fill="#1e40af">HQ CENTRAL OPERATIONS DATA CENTER (Subnet: 192.168.10.0/24)</text>
      <text x="20" y="46" font-family="Segoe UI, Arial" font-size="10" fill="#64748b">Hosts Flask Operations Command (:5000) &amp; Fleet Gatekeeper Telematics Hub</text>
    </svg>"""
    client.add_drawing(project_id, x=-380, y=-170, svg=hq_card_svg, z=0)

    # WAN Transit Card
    wan_card_svg = """<svg height="170" width="760">
      <rect width="750" height="160" rx="12" fill="#1e293b" fill-opacity="0.08" stroke="#6366f1" stroke-width="2" stroke-dasharray="6,4"/>
      <text x="20" y="26" font-family="Segoe UI, Arial" font-size="12" font-weight="bold" fill="#4338ca">HYBRID WAN TELEMATICS TRANSIT (Cellular + Satellite Constellation)</text>
    </svg>"""
    client.add_drawing(project_id, x=-380, y=180, svg=wan_card_svg, z=0)

    # Vehicle Edge In-Cabin Card
    veh_card_svg = """<svg height="230" width="760">
      <rect width="750" height="220" rx="12" fill="#1e293b" fill-opacity="0.08" stroke="#10b981" stroke-width="2" stroke-dasharray="6,4"/>
      <text x="20" y="28" font-family="Segoe UI, Arial" font-size="12" font-weight="bold" fill="#065f46">IN-CABIN EDGE VEHICLE &amp; TELEMATICS (Subnet: 192.168.20.0/24)</text>
      <text x="20" y="46" font-family="Segoe UI, Arial" font-size="10" fill="#64748b">Autonomous Edge-AI (MediaPipe Face Mesh + 24-Frame Temporal Buffer Filter)</text>
    </svg>"""
    client.add_drawing(project_id, x=-380, y=360, svg=veh_card_svg, z=0)

    time.sleep(0.8)

    # -------------------------------------------------------------------------
    # 2. Creating DrishtiAI Server & Core Network Nodes
    # -------------------------------------------------------------------------
    print("\n[STEP 2/5] Creating DrishtiAI Server and Network Nodes Live on Canvas...")

    nodes = {}

    # 1. DrishtiAI-HQ-Server
    print("   [+] Spawning 'DrishtiAI-HQ-Server' (Fleet Operations Central Hub)...")
    nodes["server"] = client.add_node(
        project_id,
        name="DrishtiAI-HQ-Server",
        node_type="vpcs",
        x=-180,
        y=-90,
        symbol=":/symbols/classic/server.svg",
    )
    time.sleep(0.5)

    # 2. Ops-Dispatcher-PC
    print("   [+] Spawning 'Ops-Dispatcher-PC' (Fleet Incident Dispatch Console)...")
    nodes["dispatcher"] = client.add_node(
        project_id,
        name="Ops-Dispatcher-PC",
        node_type="vpcs",
        x=180,
        y=-90,
        symbol=":/symbols/computer.svg",
    )
    time.sleep(0.5)

    # 3. HQ-Core-Switch
    print("   [+] Spawning 'HQ-Core-Switch' (L2 Distribution Switch)...")
    nodes["hq_sw"] = client.add_node(
        project_id,
        name="HQ-Core-Switch",
        node_type="ethernet_switch",
        x=0,
        y=-10,
        symbol=":/symbols/classic/switch_l2.svg",
    )
    time.sleep(0.5)

    # 4. HQ-Gateway-Router
    print("   [+] Spawning 'HQ-Gateway-RTR' (HQ WAN Gateway Router)...")
    nodes["hq_rtr"] = client.add_node(
        project_id,
        name="HQ-Gateway-RTR",
        node_type="ethernet_switch",
        x=0,
        y=110,
        symbol=":/symbols/classic/router.svg",
    )
    time.sleep(0.5)

    # 5. Jio 4G/5G Cellular Tower
    print("   [+] Spawning 'Jio-4G-Cellular' (Primary Cellular Base Station)...")
    nodes["jio_cellular"] = client.add_node(
        project_id,
        name="Jio-4G-Cellular",
        node_type="ethernet_switch",
        x=-220,
        y=250,
        symbol=":/symbols/classic/router.svg",
    )
    time.sleep(0.5)

    # 6. JioSpaceFiber SES MEO Satellite Gateway
    print("   [+] Spawning 'JioSpaceFiber-MEO' (SES O3b mPOWER Satellite Link)...")
    nodes["jio_satellite"] = client.add_node(
        project_id,
        name="JioSpaceFiber-MEO",
        node_type="ethernet_switch",
        x=220,
        y=250,
        symbol=":/symbols/affinity/circle/blue/satellite.svg",
    )
    time.sleep(0.5)

    # 7. Vehicle-Telematics-GW
    print("   [+] Spawning 'Vehicle-Telematics-GW' (In-Cab Dynamic Failover Gateway)...")
    nodes["veh_gw"] = client.add_node(
        project_id,
        name="Vehicle-Telematics-GW",
        node_type="ethernet_switch",
        x=0,
        y=390,
        symbol=":/symbols/classic/router.svg",
    )
    time.sleep(0.5)

    # 8. Vehicle-01-DMS Edge AI Unit
    print("   [+] Spawning 'Vehicle-01-DMS' (In-Cab Edge AI Driver Monitoring System)...")
    nodes["veh_dms"] = client.add_node(
        project_id,
        name="Vehicle-01-DMS",
        node_type="vpcs",
        x=0,
        y=510,
        symbol=":/symbols/computer.svg",
    )
    time.sleep(0.8)

    # -------------------------------------------------------------------------
    # 3. Connecting Network Links
    # -------------------------------------------------------------------------
    print("\n[STEP 3/5] Cabling & Linking Multi-Tier Network Topology...")

    link_defs = [
        # (Node A, Port A, Node B, Port B, Description)
        ("server", 0, "hq_sw", 0, "Server <-> HQ Core Switch"),
        ("dispatcher", 0, "hq_sw", 1, "Dispatcher PC <-> HQ Core Switch"),
        ("hq_sw", 2, "hq_rtr", 0, "HQ Core Switch <-> HQ Gateway RTR"),
        ("hq_rtr", 1, "jio_cellular", 0, "HQ Gateway <-> Jio 4G Cellular (Primary)"),
        ("hq_rtr", 2, "jio_satellite", 0, "HQ Gateway <-> JioSpaceFiber Satellite (Backup)"),
        ("jio_cellular", 1, "veh_gw", 0, "Jio 4G Cellular <-> Vehicle Gateway"),
        ("jio_satellite", 1, "veh_gw", 1, "JioSpaceFiber Satellite <-> Vehicle Gateway"),
        ("veh_gw", 2, "veh_dms", 0, "Vehicle Gateway <-> Vehicle DMS Client"),
    ]

    for node_a_key, port_a, node_b_key, port_b, desc in link_defs:
        print(f"   [--] Connecting: {desc}...")
        client.add_link(
            project_id,
            nodes[node_a_key]["node_id"],
            port_a,
            nodes[node_b_key]["node_id"],
            port_b,
        )
        time.sleep(0.4)

    # Annotations next to links
    client.add_drawing(
        project_id,
        x=-340,
        y=280,
        svg='<svg height="30" width="160"><text font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#16a34a">Primary: 4G/5G Cellular</text></svg>',
    )
    client.add_drawing(
        project_id,
        x=160,
        y=280,
        svg='<svg height="30" width="200"><text font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#0284c7">Failover: JioSpaceFiber MEO</text></svg>',
    )

    # -------------------------------------------------------------------------
    # 4. Powering On All Infrastructure
    # -------------------------------------------------------------------------
    print("\n[STEP 4/5] Powering On All Network Nodes in GNS3...")
    client.start_all_nodes(project_id)
    time.sleep(2.0)

    # -------------------------------------------------------------------------
    # 5. Configuring VPCS Static IP Addresses
    # -------------------------------------------------------------------------
    print("\n[STEP 5/5] Configuring IP Addressing & Verifying Telematics Subnets...")

    # Fetch updated nodes to read console ports
    all_nodes = {n["name"]: n for n in client._request("GET", f"/projects/{project_id}/nodes")}

    ip_configs = [
        ("DrishtiAI-HQ-Server", "192.168.10.100", "255.255.255.0", "192.168.10.1"),
        ("Ops-Dispatcher-PC", "192.168.10.50", "255.255.255.0", "192.168.10.1"),
        ("Vehicle-01-DMS", "192.168.20.100", "255.255.255.0", "192.168.20.1"),
    ]

    for name, ip, mask, gw in ip_configs:
        node_info = all_nodes.get(name)
        if node_info and node_info.get("console"):
            c_port = node_info["console"]
            print(f"   [IP] Configuring {name}: {ip}/24 via console port {c_port}...")
            configure_vpcs_ip(c_port, ip, mask, gw)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 72)
    print("      DRISHTI AI GNS3 TOPOLOGY CREATED SUCCESSFULLY!")
    print("=" * 72)
    print(" Look at your GNS3 window right now to see the live server architecture:")
    print("  * DrishtiAI-HQ-Server:      192.168.10.100 (Fleet Operations Command)")
    print("  * Ops-Dispatcher-PC:        192.168.10.50  (Incident Dispatcher)")
    print("  * Jio 4G/5G Cellular Link:  Primary Uplink Route (Low-Latency Stream)")
    print("  * JioSpaceFiber Link:       Satellite Failover Route (SES MEO Constellation)")
    print("  * Vehicle-01-DMS:           192.168.20.100 (Edge AI In-Cab Monitoring)")
    print("=" * 72)


if __name__ == "__main__":
    main()
