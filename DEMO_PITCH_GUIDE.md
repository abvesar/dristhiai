# DRISHTI AI — Live Pitch Demonstration Runbook
*Autonomous Edge-AI Driver Safety & Multi-Tier Satellite Telematics*

---

## 🌟 Executive Positioning & Pitch Hook

> **The Problem**: In rugged terrains like the Himalayas, Northeast corridors, and high-altitude mining passes, fleet vehicles operate in dangerous conditions—sharp hairpin curves, blind spots, driver fatigue, and frequent **complete cellular dead zones**. Existing fleet tracking and dashcam platforms fail: they either annoy drivers with false alarms on every curve, or completely go dark when 4G/5G drops.
>
> **The Solution**: **DRISHTI AI** combines real-time geometric biometrics (MediaPipe Face Mesh) with a custom-trained **Hugging Face Driver Classifier**, Edge-AI risk synthesis, temporal noise-filtering, and an intelligent **JioSpaceFiber (SES MEO Satellite)** failover architecture. Even in deep mountain gorges where cellular completely drops, critical life-safety alerts punch through with zero data loss.

---

## 👁️ Demo 1: The Live "Hairpin Bend" & Blind-Spot Simulation

### Objective
Prove to stakeholders that DRISHTI AI handles aggressive mountain physics (like Darjeeling's Hill Cart Road or Zoji La Pass) without generating annoying false alerts, yet catches genuine driver drowsiness within 1.5 seconds.

### Launch Command
```powershell
# In PowerShell:
.\launch_both_dashboards.ps1
# Or directly:
& ".\.venv\Scripts\python.exe" app.py
```
Open **`http://localhost:5000/`** in your browser.

### The Execution & Talking Points
1. **Mimic Sharp Steering & Mirror Checks**:
   - Sit in front of the webcam.
   - Turn your head sharply to the left or right (as if checking a side mirror on a hairpin turn) for ~0.5 to 0.8 seconds.
   - **Show the Audience**:
     - Point to the in-video indicator: `TEMPORAL FILTER: ABSORBING HAIRPIN/MIRROR CHECK (14/24)`.
     - Point to the dashboard progress bar: the temporal counter absorbs brief lateral head movements.
     - **The Takeaway**: *"Notice how competitor dashcams beep annoyingly during every bend. DRISHTI AI uses a 24-frame temporal buffer that accommodates necessary lateral checks without false alarms."*
2. **The Climax — Micro-Sleep / Drowsiness Detection**:
   - Close your eyes completely.
   - Watch the timer: `EYES CLOSING: 0.8s / 1.5s`.
   - The exact millisecond your eyes remain shut for **$> 1.5\text{ seconds}$**:
     - Flashing bright red borders surround the camera frame.
     - Dashboard status flashes: `🚨 CRITICAL: DROWSINESS DETECTED (EYES CLOSED > 1.5s)`.
     - In-cab audio alarm buzzer triggers.
     - Risk badge turns to **HIGH RISK** and routes priority dispatch to **JioSpaceFiber Satellite**.

---

## 📡 Demo 2: The "Deep Valley" Satellite Failover (JioSpaceFiber Pitch)

### Objective
Demonstrate how DRISHTI AI bypasses cellular dead zones in deep Himalayan valleys where competitor platforms go offline.

### Why JioSpaceFiber?
- **Regulatory Compliance**: Reliance Jio holds India's DoT GMPCS license and IN-SPACe clearances with SES O3b mPOWER MEO satellites—making it compliant with Indian national standards for road transport and defense logistics.
- **Dual-Tier Resilience**:
  - *Tier 1 (4G/5G)*: Real-time high-definition video streaming and full biometrics.
  - *Tier 2 (JioSpaceFiber Broadband Satellite)*: Transmits high-priority event telemetry and incident clips from dead zones.
  - *Tier 3 (32-byte Micro-Packet SBD)*: Ultra-compressed hex telemetry packet (`DRST|V1|R:HIG|F:drow`) that punches through steep gorge shadows.

### Launch Command
Open a terminal and run:
```powershell
& ".\.venv\Scripts\python.exe" fleet_gatekeeper_hub.py --transmission-mode hybrid --distraction-score 0.9 --speed-kph 85 --cycle-seconds 1.0
```

### The Execution & Live Cues
1. **Initial Online State (Cellular 4G/5G)**:
   - While your laptop is connected to Wi-Fi, the hub reports normal cloud routing:
     ```text
     cloud_tx driver_id=drv_001 risk=HIGH reasons=['distraction_high', 'speeding_detected']
     ```
2. **Cut Network (Disconnect Wi-Fi / Toggle Airplane Mode)**:
   - Disconnect your laptop's Wi-Fi.
   - Within **0.8 seconds**, the cellular probe detects the dead zone and switches to JioSpaceFiber:
     ```text
     ⚠️ [NETWORK CRITICAL] 4G/5G connection lost. Routing shifted to JioSpaceFiber Satellite Link.
     🛰️ [SATELLITE_TX] 4G/5G Signal Dead. Pushing compressed hex packet via JioSpaceFiber link: DRST|V1|R:HIG|F:dist
     ```
   - **Show the Audience**: *"Notice that competitor systems freeze or lose data. DRISHTI AI instantly shifts routing to JioSpaceFiber and pushes a hardened 32-byte hex telemetry packet over satellite."*
3. **Restore Network (Reconnect Wi-Fi)**:
   - Reconnect Wi-Fi.
   - The system automatically detects restoration and flushes the offline SQLite store-and-forward queue:
     ```text
     📶 [NETWORK RESTORED] 4G/5G connection restored. Routing shifted to Cloud Link.
     🔄 [STORE & FORWARD] Cellular online: Synced and drained 3 queued telemetry packets to cloud.
     store_forward_sync count=3
     ```
   - **The Takeaway**: *"Zero data loss. Even low-priority health logs cached offline during the dead zone are drained and synced to central fleet command."*

---

## 🏎️ Demo 3: Keyboard-Driven CAN-Bus Telematics & Speed Intercepts

### Objective
Demonstrate real-time vehicle telematics integration: show that looking away at cruising speed is flagged as `MODERATE` risk, but accelerating past $80\text{ km/h}$ on a mountain route escalates risk to `HIGH` and triggers satellite dispatch.

### Launch Command
You can control speed in either of two ways:
1. **Directly in the Web Dashboard (`http://localhost:5000/`)**:
   - Use the **`▲ +5 km/h`** / **`▼ -5 km/h`** buttons on-screen.
   - Or press **`Up Arrow`** / **`Down Arrow`** directly on your keyboard.
2. **Or via the Terminal CAN Controller**:
   ```powershell
   & ".\.venv\Scripts\python.exe" demo_can_telematics.py
   ```

### The Execution & Live Cues
1. **Cruising Speed ($60\text{ km/h}$)**:
   - Vehicle speed is set to $60\text{ km/h}$ (cruising speed on winding roads).
   - Turn your head away from the camera for $> 1\text{ second}$.
   - **Audience Observation**:
     - System flags: `WARNING: DISTRACTED DRIVING`.
     - Risk level: **`MODERATE RISK`** (Amber badge).
     - Transmission remains on **`Jio 4G/5G Cellular Link`**.
2. **Speed Escalation Past $80\text{ km/h}$**:
   - Press **`Up Arrow`** repeatedly until speed reaches **$85\text{ km/h}$** (or click `85 km/h (Hill Cart Rd)`).
   - Speedometer turns red: `⚠️ SPEED >= 80 km/h: OVERSPEED THRESHOLD REACHED`.
   - Now look away from the camera.
   - **The Dynamic Escalation**:
     - Combined signals: `["distraction_high", "speeding_detected"]`.
     - Risk score crosses $0.80$, immediately escalating from `MODERATE` to **`🚨 HIGH RISK`**.
     - Flashing red box around the camera frame.
     - Uplink shifts to: **`🛰️ JioSpaceFiber Satellite (Priority Uplink)`**.
     - Compact hex packet generated: `DRST|V1|R:HIG|F:dist`.

---

## 🛠️ Quick Command Reference

| Action | Command |
| :--- | :--- |
| **Launch Both Dashboards** | `.\launch_both_dashboards.ps1` |
| **Launch Flask Operations Command (Port 5000)** | `& ".\.venv\Scripts\python.exe" app.py` |
| **Launch Gradio Operations UI (Port 7860)** | `& ".\.venv\Scripts\python.exe" gradio_app.py` |
| **Run Hybrid Hub with JioSpaceFiber** | `& ".\.venv\Scripts\python.exe" fleet_gatekeeper_hub.py --transmission-mode hybrid` |
| **Run CAN Telematics Terminal Controller** | `& ".\.venv\Scripts\python.exe" demo_can_telematics.py` |
| **Run Automated Test Suite (19 Tests)** | `& ".\.venv\Scripts\python.exe" -m unittest discover tests` |
