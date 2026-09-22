"""End-to-End Fine-Tuning Pipeline for Hugging Face Driver Monitoring Classification.

Key Highlights:
- Low-memory architecture (MobileNetV2: ~14 MB) suitable for CPU environments
- Zero external torchvision dependency (self-contained PIL / NumPy tensor transforms)
- Proper dataset splitting (train / val / test)
- Classification metrics: Accuracy, Precision, Recall, Macro-F1, and Confusion Matrix
- Checkpoints exported to standard Hugging Face format
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoConfig,
    AutoModelForImageClassification,
    MobileNetV2Config,
    MobileNetV2ForImageClassification,
    MobileNetV2ImageProcessor,
)

# Limit PyTorch CPU thread memory allocation to avoid paging errors on constrained systems
torch.set_num_threads(2)
torch.set_num_interop_threads(1)

LABELS = [
    "alert_normal",
    "drowsy",
    "distracted",
    "yawning",
    "phone_use",
]

ID2LABEL = {i: name for i, name in enumerate(LABELS)}
LABEL2ID = {name: i for i, name in enumerate(LABELS)}

# Standard ImageNet normalization parameters
NORM_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
NORM_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class DriverDataset(Dataset):
    def __init__(self, root_dir: Path, augment: bool = False) -> None:
        self.samples: List[Tuple[Path, int]] = []
        self.augment = augment

        for label_name, label_id in LABEL2ID.items():
            class_dir = root_dir / label_name
            if not class_dir.exists():
                continue
            for img_path in class_dir.glob("*.jpg"):
                self.samples.append((img_path, label_id))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert("RGB")

        # In-place light photometric augmentation for training
        if self.augment:
            factor = np.random.uniform(0.88, 1.12)
            image = Image.eval(image, lambda c: min(255, int(c * factor)))

        # Standard 224x224 resize
        if image.size != (224, 224):
            image = image.resize((224, 224), Image.Resampling.BILINEAR)

        arr = np.array(image, dtype=np.float32) / 255.0
        arr = (arr - NORM_MEAN) / NORM_STD
        tensor = torch.from_numpy(arr.transpose(2, 0, 1)).float()

        return {
            "pixel_values": tensor,
            "labels": torch.tensor(label, dtype=torch.long),
        }


def compute_metrics(predictions: np.ndarray, targets: np.ndarray) -> Dict[str, object]:
    """Computes precision, recall, macro F1, and multi-class confusion matrix."""
    num_classes = len(LABELS)
    accuracy = float((predictions == targets).mean())

    confusion_matrix = np.zeros((num_classes, num_classes), dtype=int)
    for p, t in zip(predictions, targets):
        confusion_matrix[t, p] += 1

    precision_list = []
    recall_list = []
    f1_list = []

    for c in range(num_classes):
        tp = confusion_matrix[c, c]
        fp = confusion_matrix[:, c].sum() - tp
        fn = confusion_matrix[c, :].sum() - tp

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        precision_list.append(prec)
        recall_list.append(rec)
        f1_list.append(f1)

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(float(np.mean(f1_list)), 4),
        "macro_precision": round(float(np.mean(precision_list)), 4),
        "macro_recall": round(float(np.mean(recall_list)), 4),
        "per_class": {
            LABELS[i]: {
                "precision": round(precision_list[i], 4),
                "recall": round(recall_list[i], 4),
                "f1": round(f1_list[i], 4),
            }
            for i in range(num_classes)
        },
        "confusion_matrix": confusion_matrix.tolist(),
    }


def print_confusion_matrix(cm_list: List[List[int]]) -> None:
    cm = np.array(cm_list)
    print("\n--- Confusion Matrix ---")
    hdr_title = "True \\ Pred"
    header = f"{hdr_title:<15}" + "".join([f"{name[:8]:>10}" for name in LABELS])
    print(header)
    print("-" * len(header))
    for i, row in enumerate(cm):
        row_str = f"{LABELS[i]:<15}" + "".join([f"{val:>10}" for val in row])
        print(row_str)
    print("------------------------\n")


def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for batch in dataloader:
            pixel_values = batch["pixel_values"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(pixel_values=pixel_values)
            loss = criterion(outputs.logits, labels)

            total_loss += loss.item() * len(labels)
            preds = outputs.logits.argmax(dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader.dataset)
    metrics = compute_metrics(np.array(all_preds), np.array(all_targets))
    metrics["loss"] = round(avg_loss, 4)
    return metrics


def train_model(
    data_dir: str = "dataset",
    output_dir: str = "models/drishti_driver_classifier",
    base_model_id: str = "google/mobilenet_v2_1.0_224",
    epochs: int = 5,
    batch_size: int = 16,
    lr: float = 1e-3,
):
    start_time = time.time()
    base_path = Path(data_dir)
    save_path = Path(output_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[TRAIN] Initializing on device: {device} (threads={torch.get_num_threads()})")

    # 1. Datasets & Loaders
    train_dataset = DriverDataset(base_path / "train", augment=True)
    val_dataset = DriverDataset(base_path / "val", augment=False)
    test_dataset = DriverDataset(base_path / "test", augment=False)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    print(f"[DATA] Train: {len(train_dataset)} | Val: {len(val_dataset)} | Test: {len(test_dataset)}")

    # 2. Model Loading
    print(f"[MODEL] Loading lightweight architecture: {base_model_id}")
    model = AutoModelForImageClassification.from_pretrained(
        base_model_id,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )

    # Freeze backbone parameters to speed up CPU training and avoid memory spikes
    backbone = getattr(model, "mobilenet_v2", None) or getattr(model, "vit", None)
    if backbone is not None:
        for param in backbone.parameters():
            param.requires_grad = False
        print("[MODEL] Frozen backbone feature extractor. Training classification head...")

    model.to(device)

    # 3. Optimizer and Loss
    criterion = torch.nn.CrossEntropyLoss()
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=lr, weight_decay=0.01)

    best_val_f1 = 0.0
    history = []

    print(f"\n[TRAIN] Beginning training for {epochs} epochs...")
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0

        for step, batch in enumerate(train_loader, 1):
            pixel_values = batch["pixel_values"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(pixel_values=pixel_values)
            loss = criterion(outputs.logits, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * len(labels)

        train_loss = running_loss / len(train_dataset)
        val_metrics = evaluate(model, val_loader, criterion, device)

        print(
            f"Epoch {epoch:02d}/{epochs:02d} | "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f} | "
            f"Val Acc: {val_metrics['accuracy'] * 100:.1f}% | "
            f"Val Macro-F1: {val_metrics['macro_f1']:.4f}"
        )

        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "val_loss": val_metrics["loss"],
            "val_acc": val_metrics["accuracy"],
            "val_macro_f1": val_metrics["macro_f1"],
        })

        if val_metrics["macro_f1"] >= best_val_f1:
            best_val_f1 = val_metrics["macro_f1"]
            model.save_pretrained(str(save_path))

    # 4. Final Evaluation on Held-Out Test Set
    print("\n[TEST] Running final evaluation on held-out test split...")
    test_metrics = evaluate(model, test_loader, criterion, device)
    print(f"Test Loss:     {test_metrics['loss']:.4f}")
    print(f"Test Accuracy: {test_metrics['accuracy'] * 100:.2f}%")
    print(f"Test Macro-F1: {test_metrics['macro_f1']:.4f}")
    print_confusion_matrix(test_metrics["confusion_matrix"])

    # 5. Save Complete Training Report
    report = {
        "base_model": base_model_id,
        "classes": LABELS,
        "epochs": epochs,
        "training_time_seconds": round(time.time() - start_time, 2),
        "history": history,
        "test_evaluation": test_metrics,
    }
    report_file = save_path / "training_report.json"
    with report_file.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[COMPLETE] Model exported successfully to: {save_path.resolve()}")
    print(f"[COMPLETE] Evaluation report saved to: {report_file.resolve()}\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Hugging Face Driver Monitoring Model")
    parser.add_argument("--data-dir", default="dataset", help="Dataset directory")
    parser.add_argument("--output-dir", default="models/drishti_driver_classifier", help="Model export dir")
    parser.add_argument("--base-model", default="google/mobilenet_v2_1.0_224", help="Base HF model")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-3, help="Learning rate")
    args = parser.parse_args()

    train_model(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        base_model_id=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )
