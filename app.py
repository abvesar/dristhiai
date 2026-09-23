import os
import time

from flask import Flask, Response, jsonify, render_template_string, request
import cv2
import numpy as np
from ai_tracking.driver_monitor import DrishtiAIDMS

app = Flask(__name__)
dms_system = DrishtiAIDMS()

vehicle_speed_kph = 60.0

latest_telemetry = {
    "drowsy": False,
    "distracted": False,
    "yawning": False,
    "phone_usage": False,
    "driver_id": "CONNECTING...",
    "face_recognized": False,
    "face_detected": False,
    "risk_level": "NORMAL",
    "risk_score": 0.0,
    "speed_kph": 60.0,
    "overspeed": False,
    "ear": 0.0,
    "mar": 0.0,
    "yaw": 0.0,
    "distraction_counter": 0,
    "distraction_limit": 24,
    "closed_duration": 0.0,
    "satellite_provider": "JioSpaceFiber (SES MEO)",
    "network_link": "Jio 4G/5G Cellular",
    "compact_packet": "DRST|V1|R:NOR|F:none",
    "emotion": "PENDING",
    "emotion_score": 0.0,
    "reasons": [],
}

camera_source = os.environ.get("DRISHTI_CAMERA_SOURCE", "0")
if camera_source.isdigit():
    camera_source = int(camera_source)
camera = None
pipeline_error = None


def _open_camera():
    global camera
    if camera is not None and camera.isOpened():
        return camera

    if isinstance(camera_source, int):
        camera = cv2.VideoCapture(camera_source, cv2.CAP_DSHOW)
    else:
        camera = cv2.VideoCapture(camera_source)
    if not camera.isOpened():
        camera.release()
        camera = None
        return camera

    # Configure camera for real-time zero-lag streaming
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    return camera


def _placeholder_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (18, 20, 30)
    cv2.putText(frame, "DRISHTI AI CAMERA UNAVAILABLE", (75, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 180, 255), 2)
    cv2.putText(frame, "Check webcam access or DRISHTI_CAMERA_SOURCE", (42, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    return frame


def _is_black_frame(frame) -> bool:
    return float(frame.mean()) < 3.0 and int(frame.max()) < 32


def generate_frames():
    global camera, pipeline_error
    while True:
        active_camera = _open_camera()
        if active_camera is None:
            frame = _placeholder_frame()
            time.sleep(0.5)
        else:
            success, frame = active_camera.read()
            if not success:
                active_camera.release()
                camera = None
                frame = _placeholder_frame()
                time.sleep(0.5)
            else:
                alerts = None
                if _is_black_frame(frame):
                    alerts = {
                        "drowsy": False,
                        "distracted": False,
                        "face_recognized": False,
                        "driver_id": "CAMERA FRAME BLACK",
                        "drowsiness_confidence": 0.0,
                    }
                    cv2.putText(
                        frame,
                        "CAMERA INPUT IS BLACK: OPEN SHUTTER / CHECK PERMISSIONS",
                        (25, 135),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 180, 255),
                        2,
                    )
                elif pipeline_error is None:
                    try:
                        alerts = dms_system.process_frame(frame, speed_kph=vehicle_speed_kph)
                    except (FileNotFoundError, ImportError, RuntimeError) as exc:
                        pipeline_error = str(exc)

        if active_camera is None or not success or pipeline_error is not None:
            alerts = {
                "drowsy": False,
                "distracted": False,
                "face_recognized": False,
                "driver_id": "CAMERA UNAVAILABLE" if active_camera is None else "AI MODEL UNAVAILABLE",
                "drowsiness_confidence": 0.0,
                "face_detected": False,
            }
            if pipeline_error is not None and active_camera is not None and success:
                cv2.putText(
                    frame,
                    "AI MODEL UNAVAILABLE: add yolov8n-face.pt",
                    (30, 130),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 180, 255),
                    2,
                )
        if alerts["drowsy"]:
            if int(time.monotonic() * 4) % 2 == 0:
                cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (0, 0, 255), 8)
            status_text = "CRITICAL: DROWSINESS DETECTED"
            status_color = (0, 0, 255)
        elif alerts["distracted"] and vehicle_speed_kph >= 80.0:
            if int(time.monotonic() * 4) % 2 == 0:
                cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (0, 0, 255), 8)
            status_text = "CRITICAL: DISTRACTION + OVERSPEED (>= 80 km/h)"
            status_color = (0, 0, 255)
        elif alerts["distracted"]:
            status_text = "WARNING: DISTRACTED DRIVING"
            status_color = (0, 165, 255)
        elif not alerts.get("face_detected", False):
            status_text = "NO FACE DETECTED"
            status_color = (0, 180, 255)
        else:
            status_text = "MEDIAPIPE FACE MESH ACTIVE"
            status_color = (0, 255, 0)

        cv2.putText(frame, status_text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        recognition_text = alerts["driver_id"]
        recognition_color = (0, 220, 80) if alerts["face_recognized"] else (0, 80, 255)
        cv2.putText(
            frame,
            f"DRIVER ID: {recognition_text}",
            (30, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            recognition_color,
            2,
        )
        hf = alerts.get("huggingface") or {}
        hf_state = str(hf.get("label") or hf.get("emotion") or "OFF")
        hf_score = float(hf.get("score") or 0.0)
        hf_line = f"MAIN AI (HF): {hf_state}"
        if hf.get("enabled") and hf_score:
            hf_line += f" ({int(hf_score * 100)}%)"
        cv2.putText(
            frame,
            hf_line,
            (30, 125),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 240, 255) if hf.get("enabled") else (160, 160, 160),
            2,
        )

        speed_color = (0, 0, 255) if vehicle_speed_kph >= 80.0 else (0, 255, 120)
        speed_tag = " [OVERSPEED]" if vehicle_speed_kph >= 80.0 else ""
        cv2.putText(
            frame,
            f"CAN SPEED: {vehicle_speed_kph:.0f} km/h{speed_tag}",
            (max(10, frame.shape[1] - 310), 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            speed_color,
            2,
        )

        if hf.get("enabled"):
            backend = str(hf.get("backend") or "transformers").upper()
            device_name = f"HUGGING FACE ({backend}) + MEDIAPIPE"
        else:
            device_name = "MEDIAPIPE CPU"
        cv2.putText(
            frame,
            f"Device Engine: {device_name}",
            (30, frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )
        # Update live shared telemetry
        if alerts:
            edge = alerts.get("edge_ai", {})
            risk_level = str(edge.get("risk_level", "NORMAL"))
            reasons = list(edge.get("reasons", []))
            primary_reason = reasons[0][:4] if reasons else "none"
            compact_packet = f"DRST|V1|R:{risk_level[:3]}|F:{primary_reason}"
            network_link = "JioSpaceFiber Satellite (Priority Uplink)" if risk_level == "HIGH" else "Jio 4G/5G Cellular"

            latest_telemetry = {
                "drowsy": bool(alerts.get("drowsy")),
                "distracted": bool(alerts.get("distracted")),
                "yawning": bool(alerts.get("yawning")),
                "phone_usage": bool(alerts.get("phone_usage")),
                "driver_id": str(alerts.get("driver_id", "UNKNOWN")),
                "face_recognized": bool(alerts.get("face_recognized")),
                "face_detected": bool(alerts.get("face_detected")),
                "risk_level": risk_level,
                "risk_score": float(edge.get("risk_score", 0.0)),
                "speed_kph": round(vehicle_speed_kph, 1),
                "overspeed": vehicle_speed_kph >= 80.0,
                "ear": round(float(alerts.get("ear", 0.0)), 3),
                "mar": round(float(alerts.get("mar", 0.0)), 3),
                "yaw": round(float(alerts.get("yaw", 0.0)), 1),
                "distraction_counter": int(alerts.get("distraction_counter", 0)),
                "distraction_limit": 24,
                "closed_duration": round(float(alerts.get("closed_duration", 0.0)), 2),
                "satellite_provider": "JioSpaceFiber (SES MEO)",
                "network_link": network_link,
                "compact_packet": compact_packet,
                "main_ai_model": "Hugging Face",
                "hf_state": hf_state,
                "hf_score": hf_score,
                "hf_backend": str(hf.get("backend", "")),
                "hf_model": str(hf.get("model", "")),
                "emotion": hf_state,
                "emotion_score": hf_score,
                "reasons": reasons,
                "status_text": status_text,
            }

        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/telemetry')
def api_telemetry():
    return jsonify(latest_telemetry)

@app.route('/api/speed', methods=['GET', 'POST'])
def api_speed():
    global vehicle_speed_kph
    if request.method == 'POST':
        payload = request.get_json(silent=True) or {}
        if "delta" in payload:
            vehicle_speed_kph = max(0.0, min(160.0, vehicle_speed_kph + float(payload["delta"])))
        elif "speed" in payload:
            vehicle_speed_kph = max(0.0, min(160.0, float(payload["speed"])))
    return jsonify({"speed_kph": round(vehicle_speed_kph, 1), "overspeed": vehicle_speed_kph >= 80.0})

@app.route('/')
def index():
    dashboard_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>DRISHTI AI — Central Fleet & Safety Command</title>
        <style>
            :root {
                --bg: #0d0f14;
                --card-bg: #151922;
                --card-border: #232a38;
                --accent-green: #00ff88;
                --accent-amber: #ffaa00;
                --accent-red: #ff3344;
                --accent-sat: #00d4ff;
                --text-main: #f0f4fc;
                --text-muted: #8b9bb4;
            }
            * { box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: var(--bg);
                color: var(--text-main);
                margin: 0;
                padding: 24px;
            }
            .header-bar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--card-border);
                padding-bottom: 16px;
                margin-bottom: 24px;
            }
            .brand-title {
                font-size: 24px;
                font-weight: 700;
                letter-spacing: 0.5px;
                color: #ffffff;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .brand-tag {
                background: linear-gradient(135deg, #00ff88, #00b4d8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .status-pills { display: flex; gap: 10px; align-items: center; }
            .pill {
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                border: 1px solid transparent;
            }
            .pill-cellular { background: rgba(0, 255, 136, 0.12); color: var(--accent-green); border-color: rgba(0, 255, 136, 0.3); }
            .pill-satellite { background: rgba(0, 212, 255, 0.15); color: var(--accent-sat); border-color: rgba(0, 212, 255, 0.4); animation: pulse-sat 1.5s infinite; }
            .pill-critical { background: rgba(255, 51, 68, 0.2); color: var(--accent-red); border-color: var(--accent-red); animation: pulse-red 0.8s infinite; }
            @keyframes pulse-sat { 0%, 100% { box-shadow: 0 0 0 0 rgba(0, 212, 255, 0.4); } 50% { box-shadow: 0 0 16px 2px rgba(0, 212, 255, 0.6); } }
            @keyframes pulse-red { 0%, 100% { box-shadow: 0 0 0 0 rgba(255, 51, 68, 0.5); } 50% { box-shadow: 0 0 20px 4px rgba(255, 51, 68, 0.8); } }
            .grid-container {
                display: grid;
                grid-template-columns: 660px 1fr;
                gap: 24px;
                max-width: 1400px;
                margin: auto;
            }
            .card {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 14px;
                padding: 20px;
                transition: border-color 0.3s ease, box-shadow 0.3s ease;
            }
            .card-title {
                font-size: 16px;
                font-weight: 600;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.8px;
                margin-top: 0;
                margin-bottom: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .video-frame {
                width: 640px;
                height: 480px;
                border-radius: 10px;
                border: 2px solid var(--card-border);
                display: block;
                background: #000;
            }
            .demo-hint {
                margin-top: 14px;
                font-size: 13px;
                line-height: 1.5;
                color: var(--text-muted);
                background: rgba(255, 255, 255, 0.03);
                padding: 12px;
                border-radius: 8px;
                border-left: 3px solid #00b4d8;
            }
            .telemetry-row {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                font-size: 14px;
            }
            .telemetry-label { color: var(--text-muted); }
            .telemetry-value { font-weight: 600; }
            .speed-gauge {
                background: rgba(0, 0, 0, 0.25);
                border-radius: 12px;
                padding: 16px;
                text-align: center;
                margin: 16px 0;
                border: 1px solid var(--card-border);
            }
            .speed-display {
                font-size: 48px;
                font-weight: 800;
                font-variant-numeric: tabular-nums;
                color: var(--accent-green);
                line-height: 1;
            }
            .speed-unit { font-size: 16px; font-weight: 500; color: var(--text-muted); margin-left: 4px; }
            .speed-btns { display: flex; gap: 8px; justify-content: center; margin-top: 12px; }
            .btn {
                background: #232a38;
                color: #fff;
                border: 1px solid #343e52;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            .btn:hover { background: #323d50; border-color: #4a5874; }
            .btn-danger { background: #4a151b; border-color: #88222b; color: #ff8894; }
            .btn-danger:hover { background: #6b1e27; }
            .progress-bar-bg {
                background: #1e2430;
                border-radius: 6px;
                height: 12px;
                overflow: hidden;
                margin-top: 6px;
            }
            .progress-bar-fill {
                background: var(--accent-green);
                height: 100%;
                width: 0%;
                transition: width 0.15s ease, background-color 0.2s;
            }
            .packet-box {
                font-family: Consolas, monospace;
                background: #080a0e;
                color: var(--accent-sat);
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 13px;
                margin-top: 6px;
                border: 1px solid #1a2230;
            }
            .alert-banner {
                padding: 14px;
                border-radius: 8px;
                font-weight: 700;
                text-align: center;
                margin-bottom: 16px;
                display: none;
            }
            .alert-banner.active { display: block; }
            .alert-critical { background: rgba(255, 51, 68, 0.2); border: 2px solid var(--accent-red); color: #fff; animation: pulse-red 0.8s infinite; }
            .alert-moderate { background: rgba(255, 170, 0, 0.2); border: 2px solid var(--accent-amber); color: #fff; }
        </style>
    </head>
    <body>
        <div class="header-bar">
            <div class="brand-title">
                <span>DRISHTI AI</span>
                <span class="brand-tag">Central Operations Command</span>
            </div>
            <div class="status-pills">
                <span class="pill pill-cellular" id="engine-pill">MediaPipe FaceMesh + Hugging Face</span>
                <span class="pill pill-cellular" id="uplink-pill">📶 Jio 4G/5G Cellular</span>
            </div>
        </div>

        <div id="alert-banner" class="alert-banner"></div>

        <div class="grid-container">
            <!-- Left: Video Feed & Demonstration Visual Cues -->
            <div class="card" id="video-card">
                <div class="card-title">
                    <span>In-Cab Video Stream (Vehicle #VEH-001)</span>
                    <span style="font-size: 12px; color: var(--accent-green);" id="fps-indicator">● LIVE 30 FPS</span>
                </div>
                <img src="/video_feed" class="video-frame" alt="Vehicle Camera Stream" />
                <div class="demo-hint">
                    <strong>👁️ Demo 1: Mountain Hairpin & Mirror Check Simulation</strong><br>
                    Lean your head heavily to the left or right (checking mirror). The <strong>Temporal Buffer</strong> (24 frames) absorbs lateral glances without false alarms. Close your eyes for <strong>&gt; 1.5s</strong> to trigger flashing critical alert.
                </div>
            </div>

            <!-- Right: CAN Telematics, Speedometer & Satellite Failover -->
            <div class="card" id="telemetry-card">
                <div class="card-title">
                    <span>CAN-Bus Telematics & Edge AI</span>
                    <span id="risk-badge" class="pill pill-cellular">NORMAL</span>
                </div>

                <!-- Speedometer (Demo 3) -->
                <div class="speed-gauge">
                    <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">CAN-Bus Intercept Speed</div>
                    <div style="margin-top: 6px;">
                        <span class="speed-display" id="speed-display">60</span>
                        <span class="speed-unit">km/h</span>
                    </div>
                    <div id="overspeed-warning" style="color: var(--accent-amber); font-size: 12px; margin-top: 4px; display: none;">
                        ⚠️ SPEED &ge; 80 km/h: OVERSPEED THRESHOLD REACHED
                    </div>
                    <div class="speed-btns">
                        <button class="btn" onclick="adjustSpeed(-5)">▼ -5 km/h</button>
                        <button class="btn" onclick="setSpeed(60)">60 km/h</button>
                        <button class="btn" onclick="setSpeed(85)">85 km/h (Hill Cart Rd)</button>
                        <button class="btn" onclick="adjustSpeed(5)">▲ +5 km/h</button>
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 8px;">
                        Tip: You can also use <strong>Up / Down Arrow</strong> keys directly on your keyboard.
                    </div>
                </div>

                <!-- Signals & Biometrics -->
                <div class="telemetry-row">
                    <span class="telemetry-label">Driver Identity</span>
                    <span class="telemetry-value" id="driver-id" style="color: var(--accent-green);">VERIFIED (FaceID)</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">HF Driver State</span>
                    <span class="telemetry-value" id="hf-state">ANALYZING...</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Eye Aspect Ratio (EAR)</span>
                    <span class="telemetry-value" id="ear-val">0.00</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Mouth Aspect Ratio (MAR)</span>
                    <span class="telemetry-value" id="mar-val">0.00</span>
                </div>

                <!-- Hairpin Buffer & Drowsiness Tracker -->
                <div style="margin-top: 14px;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px;">
                        <span class="telemetry-label">Hairpin Turn / Mirror Temporal Filter</span>
                        <span id="counter-val">0 / 24 frames</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" id="counter-bar"></div>
                    </div>
                </div>

                <div style="margin-top: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px;">
                        <span class="telemetry-label">Eye Closure Duration</span>
                        <span id="eye-timer-val">0.0s / 1.5s</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" id="eye-timer-bar" style="background: var(--accent-amber);"></div>
                    </div>
                </div>

                <!-- Satellite Routing (Demo 2: JioSpaceFiber) -->
                <div style="margin-top: 18px; padding-top: 12px; border-top: 1px solid var(--card-border);">
                    <div style="font-size: 12px; font-weight: 700; color: var(--accent-sat); text-transform: uppercase; margin-bottom: 6px;">
                        🛰️ Satellite Failover Architecture (JioSpaceFiber)
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted);">
                        Active Routing Network: <strong id="network-link-text" style="color: #fff;">Jio 4G/5G Cellular</strong>
                    </div>
                    <div class="packet-box" id="packet-box">
                        Packet: DRST|V1|R:NOR|F:none
                    </div>
                </div>

                <!-- Interventions -->
                <div style="display: flex; gap: 8px; margin-top: 18px;">
                    <button class="btn btn-danger" style="flex: 1;" onclick="triggerCabAlarm()">🔊 Trigger In-Cab Alert</button>
                    <button class="btn" style="flex: 1; border-color: var(--accent-sat); color: var(--accent-sat);" onclick="simulateSatelliteFailover()">🛰️ Force Sat-Link</button>
                </div>
            </div>
        </div>

        <script>
            let audioCtx = null;
            function playBeep(freq = 880, duration = 0.25) {
                try {
                    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = audioCtx.createOscillator();
                    const gain = audioCtx.createGain();
                    osc.connect(gain);
                    gain.connect(audioCtx.destination);
                    osc.frequency.value = freq;
                    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
                    osc.start();
                    osc.stop(audioCtx.currentTime + duration);
                } catch(e) {}
            }

            function triggerCabAlarm() {
                playBeep(980, 0.4);
                setTimeout(() => playBeep(980, 0.4), 200);
            }

            function simulateSatelliteFailover() {
                const uplink = document.getElementById('uplink-pill');
                uplink.className = 'pill pill-satellite';
                uplink.innerText = '🛰️ JioSpaceFiber Satellite (Forced)';
                document.getElementById('network-link-text').innerText = 'JioSpaceFiber (SES MEO Satellite Link Active)';
                document.getElementById('packet-box').innerText = 'Packet: DRST|V1|R:HIG|F:manu';
            }

            function adjustSpeed(delta) {
                fetch('/api/speed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ delta: delta })
                });
            }

            function setSpeed(speed) {
                fetch('/api/speed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ speed: speed })
                });
            }

            window.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
                    e.preventDefault();
                    adjustSpeed(5);
                } else if (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') {
                    e.preventDefault();
                    adjustSpeed(-5);
                }
            });

            async function pollTelemetry() {
                try {
                    const resp = await fetch('/api/telemetry');
                    const data = await resp.json();

                    // Speed display
                    const speedDisplay = document.getElementById('speed-display');
                    speedDisplay.innerText = Math.round(data.speed_kph || 0);
                    const overspeedWarning = document.getElementById('overspeed-warning');
                    if (data.overspeed) {
                        speedDisplay.style.color = 'var(--accent-red)';
                        overspeedWarning.style.display = 'block';
                    } else {
                        speedDisplay.style.color = 'var(--accent-green)';
                        overspeedWarning.style.display = 'none';
                    }

                    // Biometrics & IDs
                    document.getElementById('driver-id').innerText = data.driver_id;
                    document.getElementById('driver-id').style.color = data.face_recognized ? 'var(--accent-green)' : 'var(--accent-red)';
                    document.getElementById('hf-state').innerText = `${data.hf_state || 'ALERT'} (${Math.round((data.hf_score || 0)*100)}%)`;
                    document.getElementById('ear-val').innerText = (data.ear || 0).toFixed(3);
                    document.getElementById('mar-val').innerText = (data.mar || 0).toFixed(3);

                    // Demo 1 Temporal Filter Progress
                    const counter = data.distraction_counter || 0;
                    document.getElementById('counter-val').innerText = `${counter} / 24 frames`;
                    const counterPercent = Math.min(100, Math.round((counter / 24) * 100));
                    const counterBar = document.getElementById('counter-bar');
                    counterBar.style.width = counterPercent + '%';
                    counterBar.style.backgroundColor = counter > 18 ? 'var(--accent-amber)' : 'var(--accent-green)';

                    // Eye closure timer
                    const closedDuration = data.closed_duration || 0;
                    document.getElementById('eye-timer-val').innerText = `${closedDuration.toFixed(1)}s / 1.5s`;
                    const eyePercent = Math.min(100, Math.round((closedDuration / 1.5) * 100));
                    const eyeBar = document.getElementById('eye-timer-bar');
                    eyeBar.style.width = eyePercent + '%';
                    eyeBar.style.backgroundColor = closedDuration >= 1.5 ? 'var(--accent-red)' : 'var(--accent-amber)';

                    // Risk Badge & Alert Banners
                    const banner = document.getElementById('alert-banner');
                    const riskBadge = document.getElementById('risk-badge');
                    const uplinkPill = document.getElementById('uplink-pill');
                    const netLinkText = document.getElementById('network-link-text');
                    const packetBox = document.getElementById('packet-box');

                    packetBox.innerText = 'Packet: ' + (data.compact_packet || 'DRST|V1|R:NOR|F:none');

                    if (data.drowsy) {
                        banner.className = 'alert-banner active alert-critical';
                        banner.innerText = '🚨 CRITICAL: DROWSINESS DETECTED (EYES CLOSED > 1.5s) — AUDIO BUZZER ACTIVE';
                        riskBadge.className = 'pill pill-critical';
                        riskBadge.innerText = 'HIGH RISK';
                        uplinkPill.className = 'pill pill-satellite';
                        uplinkPill.innerText = '🛰️ JioSpaceFiber Satellite (Priority)';
                        netLinkText.innerText = 'JioSpaceFiber (SES MEO Constellation Link)';
                        playBeep(880, 0.1);
                    } else if (data.risk_level === 'HIGH') {
                        banner.className = 'alert-banner active alert-critical';
                        banner.innerText = '🚨 CRITICAL: DISTRACTION + OVERSPEED ESCALATION (&ge; 80 km/h) — MULTI-NETWORK DISPATCH ACTIVE';
                        riskBadge.className = 'pill pill-critical';
                        riskBadge.innerText = 'HIGH RISK';
                        uplinkPill.className = 'pill pill-satellite';
                        uplinkPill.innerText = '🛰️ JioSpaceFiber Satellite (Priority)';
                        netLinkText.innerText = 'JioSpaceFiber (SES MEO Constellation Link)';
                    } else if (data.distracted) {
                        banner.className = 'alert-banner active alert-moderate';
                        banner.innerText = '⚠️ WARNING: DISTRACTED DRIVING DETECTED — KEEP EYES ON ROAD';
                        riskBadge.className = 'pill';
                        riskBadge.style.background = 'rgba(255, 170, 0, 0.2)';
                        riskBadge.style.color = 'var(--accent-amber)';
                        riskBadge.innerText = 'MODERATE RISK';
                        uplinkPill.className = 'pill pill-cellular';
                        uplinkPill.innerText = '📶 Jio 4G/5G Cellular';
                        netLinkText.innerText = 'Jio 4G/5G Cellular Link';
                    } else {
                        banner.className = 'alert-banner';
                        riskBadge.className = 'pill pill-cellular';
                        riskBadge.innerText = 'NORMAL';
                        uplinkPill.className = 'pill pill-cellular';
                        uplinkPill.innerText = '📶 Jio 4G/5G Cellular';
                        netLinkText.innerText = 'Jio 4G/5G Cellular Link';
                    }

                } catch(e) {}
            }

            setInterval(pollTelemetry, 250);
        </script>
    </body>
    </html>
    """
    return render_template_string(dashboard_html)

if __name__ == '__main__':
    port = int(os.environ.get("DRISHTI_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

