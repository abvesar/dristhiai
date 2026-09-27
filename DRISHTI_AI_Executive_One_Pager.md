# DRISHTI AI — Executive One-Pager
**Intelligent Edge Driver Monitoring & Hybrid Satellite Telematics for Heavy Commercial Fleets**  
*Author & Lead Architect: Rohit Rajesh*

---

### 1. The Big Idea
**DRISHTI AI** (*Driver Risk Identification & Safety Telematics Intelligence*) is an automotive-grade, edge-computed Driver Monitoring System (DMS) and telematics safety gateway designed for heavy commercial logistics vehicles (multi-axle trucks, tractor-trailers, long-haul buses). 

It transforms standard in-cabin hardware into an intelligent safety cockpit that actively monitors driver cognitive fatigue and distraction in real time, scales safety interventions with vehicle CAN-bus road speed, and guarantees **zero-loss remote connectivity** across cellular dead-zones via automated failover to **JioSpaceFiber (SES MEO satellite backhaul)**.

---

### 2. The Problem Statement
India's road transport accounts for over **40% of fatal heavy commercial vehicle crashes**, with driver fatigue, micro-sleep, and split-second distractions identified as the leading root causes:
* **The Fatigue Dilemma on Freight Corridors**: Long-haul commercial drivers (e.g., NH-44, NH-48) drive continuous 10–14 hour shifts under high thermal and cognitive stress, frequently falling into unmonitored micro-sleeps (closing eyes for $>1.5$ seconds at 80 km/h equates to 33+ meters of unguided 40-tonne kinetic impact).
* **The "Blackout Corridor" Blindspot**: Crucial arterial routes (Western Ghats, mining belts, rural bypasses, mountain passes) suffer from persistent 4G/5G cellular dropouts. Traditional telematics devices go completely dark, leaving dispatchers blind when accident risk is highest.
* **Bandwidth & Latency Inefficiencies**: Existing camera-based fleet systems attempt to upload raw video to the cloud for inference, resulting in unacceptable multi-second alert latencies, massive cloud bandwidth costs, and complete failure in remote terrain.

---

### 3. The Proposed Solution
DRISHTI AI solves this crisis by combining **zero-cloud edge AI** with **bandwidth-thrifty hybrid satellite telematics**:

1. **Dual-Model Edge AI Vision**:
   * **MediaPipe Biometric Pipeline**: Real-time 468-point facial landmark mesh extracting Eye Aspect Ratio (EAR), Mouth Aspect Ratio (MAR for yawning), 3D head pose (yaw/pitch/roll), and gaze direction at 30+ FPS directly on local CPU/Edge hardware.
   * **Fine-Tuned Hugging Face Transformer**: Lightweight neural classifier validating deep cognitive fatigue, phone usage, and distraction states to eliminate false positives from glasses, lighting changes, or shadows.
2. **Speed-Scaled Dynamic Risk Governor**:
   * Interfaces directly with vehicle CAN-bus speed. At 0 km/h (toll gate), looking away triggers no alarm; at 80+ km/h (highway cruise), a 1.5-second eye closure immediately triggers high-decibel in-cab acoustic alarms and rapid braking alerts.
3. **Hybrid Satellite Backhaul (JioSpaceFiber / SES O3b mPOWER)**:
   * When cellular 4G/5G drops, the system seamlessly switches to satellite without video streaming. It transmits an **ultra-compact 48-byte telemetry packet** (`DRST|V1|R:HIGH|F:DROWSY|SPD:82|LAT:...`), consuming $<1$ KB per critical incident and providing 100% geographic coverage across India.
4. **Dual-Screen Cockpit & Fleet Command Architecture**:
   * **In-Cab Cockpit**: Digital truck cluster displaying speedometer, RPM, dual pneumatic air brake PSI, and multi-stage acoustic buzzers.
   * **Fleet Operations Control Room (HQ)**: Mobile-optimized dispatcher portal that alerts managers via real-time screen flashes and smartphone haptic vibrations, allowing remote dispatchers to trigger in-cab alarms or issue mandatory rest stop directives.

---

### 4. What I Am Planning to Develop (Roadmap & Next Steps)

* **Phase 1: Automotive-Grade Embedded Edge Integration**
  * Porting the existing software stack from laptop/PC prototype to dedicated low-power automotive edge compute boards (**NVIDIA Jetson Orin Nano / NXP i.MX8**).
  * Integrating wide-angle Near-Infrared (NIR) 940nm driver-facing cameras equipped with active IR illuminators for robust night-driving accuracy through tinted sunglasses and pitch-black cabs.
* **Phase 2: Physical CAN-Bus (SAE J1939) Hardware Interfacing**
  * Building an isolated physical OBD-II / CAN-bus transceiver interface adhering to **AIS-140** and **ISO 26262** functional safety requirements to read real-time commercial vehicle steering angle, pneumatic brake pressure, and retarder telemetry.
* **Phase 3: JioSpaceFiber / Satcom Gateway Prototype Testing**
  * Establishing formal integration testing with Reliance Jio Enterprise / Jio Space Technology to interface DRISHTI AI's 48-byte compact alert payload with commercial vehicular satellite terminals (e.g., flat-panel Phased Array antennas).
* **Phase 4: Commercial Fleet Pilot Trials**
  * Deploying field evaluation units on long-haul commercial tractor-trailers (BharatBenz / Tata Prima / Ashok Leyland) on high-fatigue routes (Mumbai–Delhi / Bengaluru–Pune) to validate real-world MTBF (Mean Time Between Failures) and accident reduction rates.

---
**Contact & Commercial Inquiries**:  
**Rohit Rajesh** | Lead Architect, DRISHTI AI | [Email / LinkedIn / Phone]
