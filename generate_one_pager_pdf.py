"""Executive One-Pager PDF Generator for DRISHTI AI.

Renders a publication-grade, single-page executive overview covering:
1. The Big Idea
2. The Problem Statement
3. The Proposed Solution (Architecture & Technical Edge)
4. Planned Development & Commercial Roadmap
Outputs 'DRISHTI_AI_Executive_One_Pager.pdf'.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_PDF = PROJECT_ROOT / "DRISHTI_AI_Executive_One_Pager.pdf"


def build_one_pager_pdf(filename: Path = OUTPUT_PDF) -> Path:
    # 0.4 inch margins (28.8 pt) to fit high-density executive 1-pager cleanly
    doc = SimpleDocTemplate(
        str(filename),
        pagesize=letter,
        leftMargin=28.8,
        rightMargin=28.8,
        topMargin=26.0,
        bottomMargin=24.0,
    )

    styles = getSampleStyleSheet()

    # Color Palette
    PRIMARY = colors.HexColor("#0f172a")     # Slate 900
    ACCENT_CYAN = colors.HexColor("#0369a1") # Sky 700
    ACCENT_GREEN = colors.HexColor("#047857")# Emerald 700
    TEXT_DARK = colors.HexColor("#1e293b")   # Slate 800
    TEXT_MUTED = colors.HexColor("#475569")  # Slate 600
    CARD_BG = colors.HexColor("#f8fafc")     # Slate 50
    BORDER_COLOR = colors.HexColor("#cbd5e1")# Slate 300

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        textColor=PRIMARY,
        alignment=TA_LEFT,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.5,
        textColor=ACCENT_CYAN,
        alignment=TA_LEFT,
    )

    author_style = ParagraphStyle(
        "AuthorStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=PRIMARY,
        alignment=TA_RIGHT,
    )

    section_header_style = ParagraphStyle(
        "SecHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=PRIMARY,
        textTransform="uppercase",
        spaceBefore=0,
        spaceAfter=0,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.8,
        textColor=TEXT_DARK,
        alignment=TA_JUSTIFY,
    )

    bullet_style = ParagraphStyle(
        "BulletDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.0,
        leading=10.4,
        textColor=TEXT_DARK,
        leftIndent=10,
    )

    story = []

    # 1. Header Bar: Title on Left, Author on Right
    header_data = [
        [
            Paragraph("<b>DRISHTI AI</b> &mdash; Executive Brief", title_style),
            Paragraph("<b>Author & Lead Architect:</b><br/>Rohit Rajesh", author_style),
        ],
        [
            Paragraph("Intelligent Edge Driver Monitoring &amp; Hybrid Satellite Telematics for Heavy Commercial Fleets", subtitle_style),
            Paragraph("Commercial Vehicle Prototype | AIS-140 Ready", ParagraphStyle("SubRight", parent=author_style, fontName="Helvetica", textColor=TEXT_MUTED)),
        ],
    ]
    header_table = Table(header_data, colWidths=[400, 154])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_CYAN, spaceAfter=5, spaceBefore=2))

    # Helper function for section cards
    def create_section_header(title_text):
        return [
            Paragraph(f"<b>{title_text}</b>", section_header_style),
            HRFlowable(width="100%", thickness=0.6, color=BORDER_COLOR, spaceAfter=4, spaceBefore=1),
        ]

    # 2. The Big Idea
    story.extend(create_section_header("1. The Big Idea"))
    story.append(
        Paragraph(
            "<b>DRISHTI AI</b> (<i>Driver Risk Identification &amp; Safety Telematics Intelligence</i>) is an "
            "automotive-grade, edge-computed Driver Monitoring System (DMS) and telematics safety gateway for "
            "heavy commercial transport (multi-axle freight trucks, tractor-trailers, long-haul buses). It transforms "
            "standard vehicular cockpits into an active safety environment that continuously monitors driver fatigue "
            "and distraction, dynamically modulates risk thresholds using vehicle CAN-bus road speed, and guarantees "
            "<b>zero-loss safety connectivity</b> in remote cellular dead-zones via automated failover to <b>JioSpaceFiber "
            "(SES MEO satellite backhaul)</b>.",
            body_style,
        )
    )
    story.append(Spacer(1, 5))

    # 3. The Problem Statement
    story.extend(create_section_header("2. The Problem Statement (The Freight Corridor Crisis)"))
    problem_text = [
        "<b>Fatal Highway Micro-Sleeps:</b> Driver fatigue accounts for over <b>40% of fatal heavy commercial vehicle crashes</b> on Indian freight expressways (NH-44, NH-48). At 80 km/h, a 1.5-second micro-sleep leaves a 40-tonne tractor-trailer unguided across 33+ meters.",
        "<b>The 'Blackout Corridor' Blindspot:</b> Critical freight passages (Western Ghats, mining corridors, mountain bypasses) suffer severe 4G/5G cellular dropouts. Traditional fleet telematics go completely dark precisely when accident risk is highest.",
        "<b>Cloud Latency &amp; Satcom Cost Traps:</b> Conventional camera telematics attempt to stream raw video to the cloud for inference, incurring prohibitive satellite bandwidth costs and multi-second latencies incompatible with real-time collision prevention.",
    ]
    for p in problem_text:
        story.append(Paragraph(f"&bull; {p}", bullet_style))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 4))

    # 4. The Proposed Solution (Core Architectural Innovations)
    story.extend(create_section_header("3. The Proposed Solution: Edge Intelligence &amp; Resilient Satcom"))
    
    sol_col1 = [
        Paragraph("<b>Dual-Model Edge AI Vision</b>", ParagraphStyle("C1", parent=body_style, fontName="Helvetica-Bold", textColor=ACCENT_CYAN)),
        Paragraph("Combines real-time <b>MediaPipe 468-point FaceMesh</b> (computing EAR, MAR yawning, and 3D head pose at 30 FPS locally) cross-validated by a <b>Fine-Tuned Hugging Face Transformer</b> to eliminate false alarms from glasses or shadows.", body_style),
        Spacer(1, 3),
        Paragraph("<b>Speed-Scaled Dynamic Risk Governor</b>", ParagraphStyle("C2", parent=body_style, fontName="Helvetica-Bold", textColor=ACCENT_CYAN)),
        Paragraph("CAN-bus telematics dynamically scale risk: at 0 km/h (toll gate), looking away triggers no alarm; at 80+ km/h (highway cruise), a 1.5s eye closure instantly triggers high-decibel acoustic in-cab buzzers and brake escalation.", body_style),
    ]

    sol_col2 = [
        Paragraph("<b>Hybrid JioSpaceFiber Satellite Uplink</b>", ParagraphStyle("C3", parent=body_style, fontName="Helvetica-Bold", textColor=ACCENT_GREEN)),
        Paragraph("When cellular drops, DRISHTI AI bypasses video streaming and transmits an <b>ultra-compact 48-byte telemetry burst</b> (<code>DRST|V1|R:HIGH|F:DROWSY|SPD:82</code>) over SES MEO satellite, consuming &lt;1 KB per incident with 100% all-India coverage.", body_style),
        Spacer(1, 3),
        Paragraph("<b>Dual-Screen Operational Command</b>", ParagraphStyle("C4", parent=body_style, fontName="Helvetica-Bold", textColor=ACCENT_GREEN)),
        Paragraph("<b>Laptop/Cab:</b> Full digital truck cluster (analog speedometer, RPM, dual air brake PSI, audio buzzers).<br/><b>Evaluator Phone:</b> Scans QR code to become live Fleet HQ with haptic vibrations and remote buzzer wake-up buttons.", body_style),
    ]

    sol_table_data = [[sol_col1, sol_col2]]
    sol_table = Table(sol_table_data, colWidths=[270, 274])
    sol_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), CARD_BG),
            ("BACKGROUND", (1, 0), (1, 0), CARD_BG),
            ("BOX", (0, 0), (0, 0), 0.5, BORDER_COLOR),
            ("BOX", (1, 0), (1, 0), 0.5, BORDER_COLOR),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(sol_table)
    story.append(Spacer(1, 5))

    # 5. What I Am Planning to Develop (Roadmap)
    story.extend(create_section_header("4. What I Am Planning to Develop (Roadmap &amp; Next Steps)"))

    roadmap_items = [
        ("Phase 1: Automotive Embedded Edge Porting", "Migrate pipeline to automotive-grade edge compute (NVIDIA Jetson Orin Nano / NXP i.MX8) paired with wide-angle Near-Infrared (NIR 940nm) cameras and active IR illumination for robust night driving in pitch-black cabs."),
        ("Phase 2: Physical SAE J1939 CAN-Bus Interfacing", "Build an isolated physical OBD-II / CAN transceiver interface compliant with AIS-140 and ISO 26262 functional safety, capturing raw commercial vehicle steering angles, pneumatic air-brake reservoirs, and retarder telemetry."),
        ("Phase 3: JioSpaceFiber Satcom Terminal Integration", "Formalize technical integration testing with Reliance Jio Enterprise / Jio Space Technology to interface the 48-byte telemetry packet with commercial vehicular satellite terminals (flat-panel Phased Array antennas)."),
        ("Phase 4: Commercial Fleet Pilot Trials", "Deploy evaluation units across long-haul commercial tractor-trailers (BharatBenz / Tata Prima / Ashok Leyland) on high-fatigue freight corridors (Mumbai&ndash;Delhi NH-48) to empirically validate accident-reduction rates."),
    ]

    roadmap_table_data = []
    for title, desc in roadmap_items:
        roadmap_table_data.append([
            Paragraph(f"<b>&bull; {title}:</b> {desc}", bullet_style)
        ])

    roadmap_table = Table(roadmap_table_data, colWidths=[544])
    roadmap_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(roadmap_table)
    story.append(Spacer(1, 6))

    # 6. Footer / Contact Box
    footer_text = Paragraph(
        "<b>DRISHTI AI Technical Dossier</b> &bull; Confidential &bull; Author: <b>Rohit Rajesh</b> &bull; Prototype Live on Local Vehicle Gateway",
        ParagraphStyle("Foot", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=TEXT_MUTED, alignment=TA_CENTER)
    )
    story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=3, spaceBefore=1))
    story.append(footer_text)

    doc.build(story)
    return filename


def main():
    pdf_path = build_one_pager_pdf()
    print(f"[OK] Executive One-Pager PDF successfully created: {pdf_path}")

    # Copy to Desktop / Downloads for user convenience
    for dest_dir in [Path.home() / "Desktop", Path.home() / "Downloads"]:
        if dest_dir.exists():
            target = dest_dir / pdf_path.name
            try:
                shutil.copy2(pdf_path, target)
                print(f"[OK] Copied PDF to {target}")
            except Exception as e:
                print(f"[!] Could not copy to {dest_dir}: {e}")


if __name__ == "__main__":
    main()
