import os
import cv2
import gradio as gr
import numpy as np

from ai_tracking.driver_monitor import DrishtiAIDMS

# Initialize the Drishti AI Driver Monitoring System
dms = DrishtiAIDMS()


def track_driver(frame):
    if frame is None:
        return None, "Waiting for camera...", {}

    # Gradio provides RGB, DMS expects BGR for OpenCV processing
    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    try:
        alerts = dms.process_frame(bgr_frame)
    except Exception as exc:
        return frame, f"Error processing frame: {exc}", {"error": str(exc)}

    # Determine status banner
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
    else:
        status_text = "NORMAL - FACE TRACKED"
        color = (0, 255, 0)

    # Draw header text banner on output frame
    cv2.putText(
        bgr_frame,
        status_text,
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
    )

    driver_id = alerts.get("driver_id", "UNKNOWN")
    cv2.putText(
        bgr_frame,
        f"DRIVER: {driver_id}",
        (25, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 120) if alerts.get("face_recognized") else (0, 100, 255),
        2,
    )

    edge_ai = alerts.get("edge_ai", {})
    risk_level = edge_ai.get("risk_level", "NORMAL")
    risk_score = edge_ai.get("risk_score", 0.0)

    hf = alerts.get("huggingface") or {}
    emotion = hf.get("emotion") or "N/A"

    summary = (
        f"Status: {status_text}\n"
        f"Driver ID: {driver_id}\n"
        f"Risk Level: {risk_level} (Score: {risk_score})\n"
        f"EAR: {alerts.get('ear', 0.0):.2f} | MAR: {alerts.get('mar', 0.0):.2f}\n"
        f"Emotion: {emotion}\n"
        f"Reasons: {', '.join(edge_ai.get('reasons', []))}"
    )

    # Convert back to RGB for Gradio display
    rgb_output = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    return rgb_output, summary, alerts


with gr.Blocks(title="DRISHTI AI - Driver Monitoring System") as demo:
    gr.Markdown(
        """
        # 🚗 DRISHTI AI — Driver Monitoring System
        Real-time facial tracking, fatigue analysis, distraction detection, and risk scoring via MediaPipe Face Mesh and Edge AI.
        """
    )

    with gr.Row():
        camera = gr.Image(
            sources=["webcam"],
            type="numpy",
            streaming=True,
            label="Live Camera Input",
        )
        tracked = gr.Image(
            label="Tracked Output (Mesh & Bounding Box)",
            type="numpy",
        )

    with gr.Row():
        status_box = gr.Textbox(
            label="Driver Status Summary",
            value="Waiting for camera...",
            interactive=False,
            lines=6,
        )
        telemetry_box = gr.JSON(
            label="Real-time Telemetry & Risk Signals",
        )

    camera.stream(
        fn=track_driver,
        inputs=camera,
        outputs=[tracked, status_box, telemetry_box],
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
