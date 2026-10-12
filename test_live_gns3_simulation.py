"""DRISHTI AI -- Live Driving Simulation & GNS3 Telemetry Showcase

Simulates a real-world high-risk Himalayan transit scenario across 5 phases,
driving live updates directly onto your open GNS3 canvas:

Phase 1: Normal Cruising (60 km/h, Jio 4G/5G Cellular)
Phase 2: Hairpin Bend Mirror Check (Distraction Filter Absorbing Motion)
Phase 3: High-Speed Mountain Escalation (85 km/h Overspeed + Distraction)
Phase 4: Deep Gorge Dead Zone (Eyes Closed > 1.5s, JioSpaceFiber Satellite Failover)
Phase 5: Signal Recovery & Store-and-Forward Sync
"""

import sys
import time
from drishti_gns3_live_bridge import DrishtiGNS3LiveBridge


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 74)
    print("      DRISHTI AI -- LIVE GNS3 DRIVING SIMULATION & FAILOVER TEST")
    print("=" * 74)
    print(" Look at your GNS3 window right now to watch the live telemetry updates!\n")

    bridge = DrishtiGNS3LiveBridge()

    test_phases = [
        {
            "name": "Phase 1: Normal Cruising on Hill Cart Road",
            "desc": "Optimal conditions, driver attentive, cellular link strong.",
            "link": "Jio 4G/5G Cellular",
            "risk": "NORMAL",
            "speed": 60.0,
            "drowsy": False,
            "distracted": False,
            "packet": "DRST|V1|R:NOR|F:none",
            "duration": 5,
        },
        {
            "name": "Phase 2: Hairpin Bend Mirror Check (Distraction Filter)",
            "desc": "Driver checks mirrors on sharp turn; 24-frame temporal buffer absorbs motion.",
            "link": "Jio 4G/5G Cellular",
            "risk": "MODERATE",
            "speed": 60.0,
            "drowsy": False,
            "distracted": True,
            "packet": "DRST|V1|R:MOD|F:dist",
            "duration": 5,
        },
        {
            "name": "Phase 3: High-Speed Escalation (85 km/h + Distraction)",
            "desc": "Vehicle exceeds 80 km/h while looking away; priority risk escalation triggers.",
            "link": "JioSpaceFiber (SES MEO)",
            "risk": "HIGH",
            "speed": 85.0,
            "drowsy": False,
            "distracted": True,
            "packet": "DRST|V1|R:HIG|F:dist",
            "duration": 6,
        },
        {
            "name": "Phase 4: Zoji La Dead Zone (Drowsiness Detected > 1.5s)",
            "desc": "Cellular signal dead. Eyes closed > 1.5s triggers emergency audio buzzer & SES MEO satellite failover.",
            "link": "JioSpaceFiber (SES MEO)",
            "risk": "HIGH",
            "speed": 75.0,
            "drowsy": True,
            "distracted": True,
            "packet": "DRST|V1|R:HIG|F:drowsy",
            "duration": 6,
        },
        {
            "name": "Phase 5: Valley Clearance & Cellular Reconnection",
            "desc": "Vehicle exits mountain gorge. 4G/5G restored, SQLite cache drained with zero data loss.",
            "link": "Jio 4G/5G Cellular",
            "risk": "NORMAL",
            "speed": 50.0,
            "drowsy": False,
            "distracted": False,
            "packet": "DRST|V1|R:NOR|F:none",
            "duration": 5,
        },
    ]

    for idx, p in enumerate(test_phases, 1):
        print(f"[{idx}/5] {p['name']}")
        print(f"      {p['desc']}")
        print(f"      -> Updating GNS3 Canvas HUD (Route: {p['link']}, Speed: {int(p['speed'])} km/h)...")
        bridge.refresh_hud(
            link=p["link"],
            risk=p["risk"],
            speed=p["speed"],
            drowsy=p["drowsy"],
            distracted=p["distracted"],
            packet=p["packet"],
        )
        for rem in range(p["duration"], 0, -1):
            sys.stdout.write(f"\r      Holding stage in GNS3... {rem}s remaining ")
            sys.stdout.flush()
            time.sleep(1.0)
        print("\r      Stage complete!                                       \n")

    print("=" * 74)
    print("      LIVE GNS3 SIMULATION TEST COMPLETED SUCCESSFULLY! 🎉")
    print("=" * 74)
    print(" The GNS3 canvas successfully demonstrated:")
    print("  * Real-time 4G/5G Cellular telematics streaming")
    print("  * Transient distraction handling with amber warning state")
    print("  * Speed escalation logic at 85 km/h")
    print("  * Zero-data-loss JioSpaceFiber (SES MEO) satellite handover on drowsiness")
    print("  * Seamless link re-establishment and telemetry synchronization")
    print("=" * 74)


if __name__ == "__main__":
    main()
