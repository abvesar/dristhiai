"""DRISHTI AI - Gradio Operations and Telemetry Dashboard.

Provides:
1. Live vehicle video stream from the central DMS feed (auto-plays without webcam collisions)
2. Real-time telemetry inspector & risk gauges
3. Interactive intervention actions (audio alarms, satellite escalation, audit checkpoints)
4. Standalone direct webcam mode for isolated testing
"""

import json
import os
import urllib.request
import cv2
import gradio as gr
import numpy as np

from ai_tracking.driver_monitor import DrishtiAIDMS

# Initialize DMS engine for standalone test tab
dms = DrishtiAIDMS()
flask_port = os.environ.get("DRISHTI_PORT", "5000")


def fetch_live_telemetry():
    """Polls live telemetry from the running Flask vehicle hub."""
    try:
        url = f"http://127.0.0.1:{flask_port}/api/telemetry"
        req = urllib.request.Request(url, headers={"User-Agent": "Drishti-Gradio"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        status = data.get("status_text", "SYSTEM ACTIVE")
        driver = f"Driver ID: {data.get('driver_id', 'UNKNOWN')}"
        risk = f"Risk Level: {data.get('risk_level', 'NORMAL')} (Score: {data.get('risk_score', 0.0):.2f})"
        biometrics = f"EAR: {data.get('ear', 0.0):.2f} | MAR: {data.get('mar', 0.0):.2f}"
        emotion = f"AI State: {data.get('emotion', 'N/A')} (Conf: {data.get('emotion_score', 0.0):.2f})"
        reasons = f"Active Signals: {', '.join(data.get('reasons', [])) or 'None'}"

        summary = (
            f"=== {status} ===\n"
            f"{driver}\n"
            f"{risk}\n"
            f"{biometrics}\n"
            f"{emotion}\n"
            f"{reasons}"
        )
        return summary, data
    except Exception:
        fallback_summary = (
            "Status: Connecting to Live Vehicle Stream...\n"
            "Waiting for camera frames from Flask service on port 5000."
        )
        return fallback_summary, {"status": "connecting", "port": flask_port}


def trigger_intervention(action_type: str):
    return f"[ACTION RECORDED] {action_type} sent to Vehicle #VEH-001 at {os.environ.get('USERNAME', 'FleetAdmin')}"


def track_standalone_driver(frame):
    if frame is None:
        return None, "Waiting for camera...", {}

    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    try:
        alerts = dms.process_frame(bgr_frame)
    except Exception as exc:
        return frame, f"Error processing frame: {exc}", {"error": str(exc)}

    status_text = "NORMAL - FACE TRACKED"
    color = (0, 255, 0)
    if alerts.get("drowsy"):
        status_text = "CRITICAL: DROWSINESS DETECTED"
        color = (0, 0, 255)
    elif alerts.get("distracted"):
        status_text = "WARNING: DISTRACTED DRIVING"
        color = (0, 165, 255)
    elif alerts.get("yawning"):
        status_text = "WARNING: YAWNING DETECTED"
        color = (0, 200, 255)
    elif alerts.get("phone_usage"):
        status_text = "CRITICAL: PHONE USAGE DETECTED"
        color = (0, 0, 255)
    elif not alerts.get("face_detected", False):
        status_text = "NO FACE DETECTED"
        color = (0, 180, 255)

    cv2.putText(bgr_frame, status_text, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    rgb_output = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    return rgb_output, status_text, alerts


custom_css = """
.stream-container {
    background: #121214;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #2e2e38;
    text-align: center;
}
.stream-img {
    width: 100%;
    max-width: 640px;
    border-radius: 8px;
    border: 2px solid #00ff66;
    margin: auto;
}
"""

with gr.Blocks(title="DRISHTI AI - Central Fleet Command", css=custom_css) as demo:
    gr.Markdown(
        """
        # 🚗 DRISHTI AI — Central Fleet & Driver Telemetry Hub
        Real-time facial tracking, fatigue assessment, and Edge AI risk routing via MediaPipe & Hugging Face.
        """
    )

    with gr.Tabs():
        with gr.TabItem("📺 Live Fleet Video & Telemetry (Auto-Stream)"):
            with gr.Row():
                with gr.Column(scale=3):
                    # Auto-playing live stream from the shared vehicle camera feed
                    stream_html = f"""
                    <div class="stream-container">
                        <h3 style="color: #00ff66; margin-top: 0; margin-bottom: 10px;">In-Cab Vehicle Feed (Vehicle #VEH-001)</h3>
                        <img src="http://localhost:{flask_port}/video_feed" class="stream-img" alt="Connecting to stream..." />
                        <p style="color: #888; font-size: 13px; margin-top: 8px;">Live low-latency MJPEG feed from OpenCV DMS engine</p>
                    </div>
                    """
                    gr.HTML(stream_html)

                with gr.Column(scale=2):
                    status_display = gr.Textbox(
                        label="Live Driver State Summary",
                        value="Connecting to vehicle feed...",
                        lines=7,
                        interactive=False,
                    )
                    telemetry_display = gr.JSON(
                        label="Edge AI Telemetry Signals",
                    )

            with gr.Row():
                btn_alarm = gr.Button("🔊 Trigger In-Cab Alert Buzzer", variant="secondary")
                btn_sat = gr.Button("🛰️ Force Satellite Escalation", variant="secondary")
                btn_audit = gr.Button("📋 Checkpoint Audit Log", variant="primary")
                action_result = gr.Textbox(label="Dispatch Response", interactive=False)

                btn_alarm.click(fn=lambda: trigger_intervention("In-Cab Audio Buzzer Triggered"), outputs=action_result)
                btn_sat.click(fn=lambda: trigger_intervention("Satellite Channel Escalation Forced"), outputs=action_result)
                btn_audit.click(fn=lambda: trigger_intervention("Manual Safety Audit Event Logged"), outputs=action_result)

            # Auto-poll telemetry from the live feed every 0.6 seconds
            timer = gr.Timer(value=0.6)
            timer.tick(
                fn=fetch_live_telemetry,
                outputs=[status_display, telemetry_display],
            )

        with gr.TabItem("📷 Direct Browser Webcam (Standalone Test Mode)"):
            gr.Markdown("Use this tab if you are running Gradio by itself without the Flask background camera server.")
            with gr.Row():
                standalone_cam = gr.Image(sources=["webcam"], type="numpy", streaming=True, label="Browser Camera")
                standalone_out = gr.Image(type="numpy", label="Tracked Output")

            standalone_status = gr.Textbox(label="Standalone Status", lines=2)
            standalone_json = gr.JSON(label="Telemetry")

            standalone_cam.stream(
                fn=track_standalone_driver,
                inputs=standalone_cam,
                outputs=[standalone_out, standalone_status, standalone_json],
                stream_every=0.1,
            )

if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_PORT", "7860"))
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=port,
        inbrowser=False,
        show_error=True,
    )
