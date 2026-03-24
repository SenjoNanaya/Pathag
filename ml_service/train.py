"""
Fine-tune MobileNetV3-small on folder-organized images (ImageFolder).

Expected layout (snake_case folder names = class labels):

    data_root/
      train/
        smooth/ *.jpg
        cracked/
        uneven/
        obstructed/
        no_sidewalk/
        under_construction/
      val/
        smooth/
        ...

Map Project Sidewalk–style exports into these buckets before training.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from torchvision.models import MobileNet_V3_Small_Weights

from ml_service.labels import PATH_CONDITION_CLASS_ORDER
from ml_service.model import build_mobilenet_v3_path_classifier, save_checkpoint


def _label_remap_tensor(class_to_idx: dict[str, int]) -> torch.Tensor:
    """Map ImageFolder alphabetical indices to PATH_CONDITION_CLASS_ORDER indices."""
    n = len(class_to_idx)
    remap = torch.zeros(n, dtype=torch.long)
    for our_idx, name in enumerate(PATH_CONDITION_CLASS_ORDER):
        if name not in class_to_idx:
            raise SystemExit(
                f"Missing training subfolder {name!r}. "
                f"Required folders: {list(PATH_CONDITION_CLASS_ORDER)}"
            )
        alf_idx = class_to_idx[name]
        remap[alf_idx] = our_idx
    return remap


def _make_loaders(
    train_dir: Path,
    val_dir: Path,
    batch_size: int,
    num_workers: int,
) -> tuple[DataLoader, DataLoader, torch.Tensor]:
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    train_tf = weights.transforms()
    val_tf = weights.transforms()

    train_ds = ImageFolder(str(train_dir), transform=train_tf)
    val_ds = ImageFolder(str(val_dir), transform=val_tf)

    found_train = set(train_ds.class_to_idx.keys())
    required = set(PATH_CONDITION_CLASS_ORDER)
    if found_train != required:
        raise SystemExit(
            f"Train folder names must match exactly (snake_case).\n"
            f"Found: {sorted(found_train)}\n"
            f"Required: {sorted(required)}"
        )
    if set(val_ds.class_to_idx.keys()) != required:
        raise SystemExit(
            f"Val folder names must match train.\n"
            f"Found: {sorted(val_ds.class_to_idx.keys())}"
        )

    remap = _label_remap_tensor(train_ds.class_to_idx)

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    return train_loader, val_loader, remap


def run_training(
    *,
    train_dir: Path,
    val_dir: Path,
    output_path: Path,
    epochs: int,
    lr: float,
    batch_size: int,
    num_workers: int,
    freeze_backbone_epochs: int,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_mobilenet_v3_path_classifier(pretrained_backbone=True).to(device)
    criterion = nn.CrossEntropyLoss()

    train_loader, val_loader, label_remap = _make_loaders(
        train_dir, val_dir, batch_size=batch_size, num_workers=num_workers
    )
    label_remap = label_remap.to(device)

    for epoch in range(epochs):
        if epoch < freeze_backbone_epochs:
            for p in model.features.parameters():
                p.requires_grad = False
        else:
            for p in model.features.parameters():
                p.requires_grad = True

        params = [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.AdamW(params, lr=lr)

        model.train()
        running = 0.0
        for images, labels in train_loader:
            images = images.to(device)
            labels = label_remap[labels].to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            running += loss.item()

        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = label_remap[labels].to(device)
                logits = model(images)
                pred = logits.argmax(dim=1)
                correct += int((pred == labels).sum().item())
                total += labels.numel()
        acc = correct / max(total, 1)
        print(
            f"epoch {epoch + 1}/{epochs} "
            f"train_loss={running / max(len(train_loader), 1):.4f} "
            f"val_acc={acc:.4f}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_checkpoint(model, str(output_path))
    print(f"Saved checkpoint to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transfer-learn MobileNetV3 for path conditions.")
    parser.add_argument("--train_dir", type=Path, required=True)
    parser.add_argument("--val_dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("ml_service/weights/path_mobilenet_v3.pt"))
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--freeze_backbone_epochs", type=int, default=1)
    args = parser.parse_args()

    run_training(
        train_dir=args.train_dir,
        val_dir=args.val_dir,
        output_path=args.output,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        freeze_backbone_epochs=args.freeze_backbone_epochs,
    )


if __name__ == "__main__":
    main()
