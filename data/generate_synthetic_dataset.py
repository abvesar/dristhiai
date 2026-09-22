"""Procedural Synthetic Driver Monitoring Dataset Generator for DRISHTI AI.

Generates structured image sets categorized into 5 safety classes:
- alert_normal
- drowsy
- distracted
- yawning
- phone_use
Under variable driving conditions (day, night, dashboard glare, motion blur).
"""

from __future__ import annotations

import argparse
import math
import os
import random
from pathlib import Path
import cv2
import numpy as np


CLASSES = [
    "alert_normal",
    "drowsy",
    "distracted",
    "yawning",
    "phone_use",
]


def create_base_canvas(size: int = 224, lighting: str = "day") -> np.ndarray:
    """Create a driving cockpit background with realistic vehicle interior ambiance."""
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    if lighting == "day":
        # Neutral vehicle interior with soft daylight gradient
        top_color = (180, 190, 200)
        bot_color = (40, 45, 55)
    elif lighting == "night":
        # Dark cabin with faint blue dashboard/instrument cluster backlight
        top_color = (25, 25, 35)
        bot_color = (15, 20, 45)
    else:  # sunset/warm glare
        top_color = (140, 160, 210)
        bot_color = (45, 45, 60)

    for y in range(size):
        ratio = y / size
        color = [int(top_color[c] * (1 - ratio) + bot_color[c] * ratio) for c in range(3)]
        canvas[y, :] = color
    return canvas


def draw_face(
    canvas: np.ndarray,
    state: str,
    skin_tone: tuple[int, int, int],
    yaw: float = 0.0,
    pitch: float = 0.0,
) -> np.ndarray:
    """Procedurally renders a driver face on the canvas with specific driver state expressions."""
    h, w = canvas.shape[:2]
    center_x = int(w * 0.5 + yaw * 30.0)
    center_y = int(h * 0.52 + pitch * 20.0)
    face_w = int(w * 0.32)
    face_h = int(h * 0.42)

    # 1. Head / Face Oval
    cv2.ellipse(
        canvas,
        (center_x, center_y),
        (face_w, face_h),
        angle=int(yaw * 10),
        startAngle=0,
        endAngle=360,
        color=skin_tone,
        thickness=-1,
    )

    # 2. Hair cap
    hair_color = (random.randint(15, 40), random.randint(15, 35), random.randint(20, 40))
    cv2.ellipse(
        canvas,
        (center_x, center_y - int(face_h * 0.55)),
        (int(face_w * 1.05), int(face_h * 0.5)),
        angle=int(yaw * 5),
        startAngle=180,
        endAngle=360,
        color=hair_color,
        thickness=-1,
    )

    # 3. Eye Coordinates
    eye_offset_x = int(face_w * 0.45)
    eye_offset_y = int(face_h * 0.15)
    left_eye_center = (center_x - eye_offset_x + int(yaw * 5), center_y - eye_offset_y)
    right_eye_center = (center_x + eye_offset_x + int(yaw * 5), center_y - eye_offset_y)

    eye_w = max(6, int(face_w * 0.22))

    if state == "drowsy":
        # Eyelids drooping or completely closed (slit / arc)
        cv2.ellipse(canvas, left_eye_center, (eye_w, 2), 0, 0, 180, (40, 40, 50), 2)
        cv2.ellipse(canvas, right_eye_center, (eye_w, 2), 0, 0, 180, (40, 40, 50), 2)
    elif state == "distracted":
        # Looking sharply to the side
        for eye_pt in (left_eye_center, right_eye_center):
            cv2.ellipse(canvas, eye_pt, (eye_w, 6), 0, 0, 360, (245, 245, 245), -1)
            pupil_offset = 5 if yaw >= 0 else -5
            cv2.circle(canvas, (eye_pt[0] + pupil_offset, eye_pt[1]), 3, (25, 20, 15), -1)
    else:  # alert_normal, yawning, phone_use
        for eye_pt in (left_eye_center, right_eye_center):
            cv2.ellipse(canvas, eye_pt, (eye_w, 7), 0, 0, 360, (250, 250, 250), -1)
            cv2.circle(canvas, eye_pt, 3, (30, 25, 20), -1)

    # Eyebrows
    for brow_pt in ((left_eye_center[0], left_eye_center[1] - 10), (right_eye_center[0], right_eye_center[1] - 10)):
        cv2.line(canvas, (brow_pt[0] - eye_w, brow_pt[1]), (brow_pt[0] + eye_w, brow_pt[1] - 2), hair_color, 2)

    # 4. Nose
    nose_tip = (center_x + int(yaw * 8), center_y + int(face_h * 0.12))
    cv2.line(canvas, (center_x, center_y - 2), nose_tip, (max(0, skin_tone[0] - 30), max(0, skin_tone[1] - 30), max(0, skin_tone[2] - 30)), 2)

    # 5. Mouth / Yawning
    mouth_y = center_y + int(face_h * 0.5)
    mouth_x = center_x + int(yaw * 6)

    if state == "yawning":
        # Deep open oval mouth
        cv2.ellipse(canvas, (mouth_x, mouth_y), (int(face_w * 0.35), int(face_h * 0.28)), 0, 0, 360, (20, 15, 30), -1)
        # Tongue hint
        cv2.ellipse(canvas, (mouth_x, mouth_y + 8), (int(face_w * 0.2), 6), 0, 0, 180, (60, 60, 140), -1)
    elif state == "drowsy":
        # Slightly slack mouth
        cv2.ellipse(canvas, (mouth_x, mouth_y), (int(face_w * 0.25), 4), 0, 0, 360, (60, 60, 110), -1)
    else:
        # Neutral closed lips
        cv2.line(canvas, (mouth_x - int(face_w * 0.25), mouth_y), (mouth_x + int(face_w * 0.25), mouth_y), (60, 60, 120), 2)

    # 6. Phone use occlusion
    if state == "phone_use":
        side = 1 if yaw >= 0 else -1
        phone_x = center_x + side * int(face_w * 0.75)
        phone_y = center_y + int(face_h * 0.1)
        # Smartphone body
        cv2.rectangle(canvas, (phone_x - 14, phone_y - 36), (phone_x + 14, phone_y + 36), (20, 20, 22), -1)
        # Phone screen glow
        cv2.rectangle(canvas, (phone_x - 11, phone_y - 32), (phone_x + 11, phone_y + 32), (180, 210, 240), -1)
        # Hand / fingers holding phone
        for f_offset in (-18, -6, 6, 18):
            cv2.ellipse(canvas, (phone_x - side * 8, phone_y + f_offset), (8, 4), 0, 0, 360, skin_tone, -1)

    return canvas


def apply_driving_distortions(image: np.ndarray) -> np.ndarray:
    """Applies realistic vehicular optical augmentations."""
    # 1. Subtle Gaussian Noise
    noise = np.random.normal(0, 3.5, image.shape).astype(np.int16)
    noisy_img = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # 2. Random slight illumination shift
    gamma = random.uniform(0.85, 1.18)
    table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255 for i in np.arange(0, 256)]).astype("uint8")
    noisy_img = cv2.LUT(noisy_img, table)

    # 3. Occasional motion blur (1 in 4 samples)
    if random.random() < 0.25:
        ksize = random.choice([3, 5])
        kernel = np.zeros((ksize, ksize))
        kernel[int((ksize - 1) / 2), :] = np.ones(ksize)
        kernel = kernel / ksize
        noisy_img = cv2.filter2D(noisy_img, -1, kernel)

    return noisy_img


def generate_sample(state: str, size: int = 224) -> np.ndarray:
    """Generates a single synthetic driver image for a designated safety state."""
    lighting = random.choice(["day", "day", "night", "glare"])
    canvas = create_base_canvas(size=size, lighting=lighting)

    # Varied natural human skin tones
    skin_tones = [
        (130, 160, 215),  # light beige
        (100, 140, 190),  # tan
        (75, 110, 165),   # medium brown
        (50, 75, 120),    # dark brown
        (150, 180, 230),  # pale
    ]
    skin_tone = random.choice(skin_tones)

    # Adjust yaw and pitch based on safety state
    if state == "distracted":
        yaw = random.choice([random.uniform(-1.0, -0.6), random.uniform(0.6, 1.0)])
        pitch = random.uniform(-0.5, 0.5)
    elif state == "drowsy":
        yaw = random.uniform(-0.25, 0.25)
        pitch = random.uniform(0.3, 0.8)  # nodding downwards
    elif state == "phone_use":
        yaw = random.choice([random.uniform(-0.6, -0.3), random.uniform(0.3, 0.6)])
        pitch = random.uniform(0.2, 0.5)
    else:  # alert_normal, yawning
        yaw = random.uniform(-0.2, 0.2)
        pitch = random.uniform(-0.15, 0.15)

    face_frame = draw_face(canvas, state=state, skin_tone=skin_tone, yaw=yaw, pitch=pitch)
    final_frame = apply_driving_distortions(face_frame)
    return final_frame


def build_dataset(
    output_dir: str = "dataset",
    train_count: int = 100,
    val_count: int = 25,
    test_count: int = 25,
) -> None:
    """Generates partitioned train/val/test splits following ML best practices."""
    splits = {
        "train": train_count,
        "val": val_count,
        "test": test_count,
    }

    base_path = Path(output_dir)
    print(f"Generating synthetic driver monitoring dataset at: {base_path.resolve()}")

    total_images = 0
    for split_name, count in splits.items():
        for state in CLASSES:
            folder = base_path / split_name / state
            folder.mkdir(parents=True, exist_ok=True)
            for idx in range(count):
                img = generate_sample(state=state, size=224)
                file_path = folder / f"{state}_{idx:04d}.jpg"
                cv2.imwrite(str(file_path), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
                total_images += 1

    print(f"Dataset generation complete! Created {total_images} total images across 5 classes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Driver Dataset Generator")
    parser.add_argument("--output-dir", default="dataset", help="Output directory path")
    parser.add_argument("--train-per-class", type=int, default=100, help="Train samples per class")
    parser.add_argument("--val-per-class", type=int, default=25, help="Val samples per class")
    parser.add_argument("--test-per-class", type=int, default=25, help="Test samples per class")
    args = parser.parse_args()

    build_dataset(
        output_dir=args.output_dir,
        train_count=args.train_per_class,
        val_count=args.val_per_class,
        test_count=args.test_per_class,
    )
