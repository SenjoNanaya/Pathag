from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Optional, Sequence

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision.datasets import ImageFolder
from torchvision.models import MobileNet_V3_Small_Weights

from ml_service.binary_verifier_labels import BINARY_VERIFIER_CLASS_ORDER
from ml_service.model import build_mobilenet_v3_binary_classifier, save_checkpoint


def _label_remap_tensor(class_to_idx: dict[str, int], class_order: Sequence[str]) -> torch.Tensor:
    """
    Map ImageFolder alphabetical indices to the configured binary class order.
    """
    n = len(class_to_idx)
    remap = torch.zeros(n, dtype=torch.long)
    for our_idx, name in enumerate(class_order):
        if name not in class_to_idx:
            raise SystemExit(
                f"Missing training subfolder {name!r}. "
                f"Required folders: {list(class_order)}"
            )
        alf_idx = class_to_idx[name]
        remap[alf_idx] = our_idx
    return remap


def _make_loaders(
    train_dir: Path,
    val_dir: Path,
    batch_size: int,
    num_workers: int,
    use_weighted_sampling: bool,
    class_order: Sequence[str],
) -> tuple[DataLoader, DataLoader, torch.Tensor, torch.Tensor]:
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    train_tf = weights.transforms()
    val_tf = weights.transforms()

    train_ds = ImageFolder(str(train_dir), transform=train_tf, allow_empty=True)
    val_ds = ImageFolder(str(val_dir), transform=val_tf, allow_empty=True)

    found_train = set(train_ds.class_to_idx.keys())
    required = set(class_order)
    if found_train != required:
        raise SystemExit(
            "Train folder names must match exactly (snake_case).\n"
            f"Found: {sorted(found_train)}\n"
            f"Required: {sorted(required)}"
        )

    if set(val_ds.class_to_idx.keys()) != required:
        raise SystemExit(
            "Val folder names must match train.\n"
            f"Found: {sorted(val_ds.class_to_idx.keys())}"
        )

    remap = _label_remap_tensor(train_ds.class_to_idx, class_order)
    n_classes = len(class_order)
    train_class_counts = torch.zeros(n_classes, dtype=torch.long)
    for _, raw_idx in train_ds.samples:
        mapped = int(remap[raw_idx].item())
        train_class_counts[mapped] += 1

    sampler: Optional[WeightedRandomSampler] = None
    if use_weighted_sampling:
        sample_weights = []
        for _, raw_idx in train_ds.samples:
            mapped = int(remap[raw_idx].item())
            count = int(train_class_counts[mapped].item())
            weight = 1.0 / max(count, 1)
            sample_weights.append(weight)
        sampler = WeightedRandomSampler(
            weights=torch.tensor(sample_weights, dtype=torch.double),
            num_samples=len(sample_weights),
            replacement=True,
        )

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=sampler is None,
        sampler=sampler,
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
    return train_loader, val_loader, remap, train_class_counts


def run_binary_training(
    *,
    train_dir: Path,
    val_dir: Path,
    output_path: Path,
    epochs: int,
    lr: float,
    batch_size: int,
    num_workers: int,
    freeze_backbone_epochs: int,
    use_class_weighted_loss: bool,
    use_weighted_sampling: bool,
    early_stopping_patience: int,
    class_order: Sequence[str],
    model_builder: Callable[..., nn.Module],
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model_builder(pretrained_backbone=True).to(device)

    train_loader, val_loader, label_remap, train_class_counts = _make_loaders(
        train_dir,
        val_dir,
        batch_size=batch_size,
        num_workers=num_workers,
        use_weighted_sampling=use_weighted_sampling,
        class_order=class_order,
    )
    label_remap = label_remap.to(device)
    class_weight_tensor: Optional[torch.Tensor] = None
    if use_class_weighted_loss:
        counts = train_class_counts.float()
        inv = torch.where(counts > 0, 1.0 / counts, torch.zeros_like(counts))
        inv_sum = float(inv.sum().item())
        if inv_sum > 0:
            class_weight_tensor = (inv / inv_sum * len(class_order)).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weight_tensor)

    best_val_acc = -1.0
    best_state_dict = None
    best_epoch = 0
    epochs_without_improvement = 0

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
        per_class_correct = torch.zeros(len(class_order), dtype=torch.long)
        per_class_total = torch.zeros(len(class_order), dtype=torch.long)
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = label_remap[labels].to(device)

                logits = model(images)
                pred = logits.argmax(dim=1)
                correct += int((pred == labels).sum().item())
                total += labels.numel()
                for i in range(labels.numel()):
                    label_i = int(labels[i].item())
                    pred_i = int(pred[i].item())
                    per_class_total[label_i] += 1
                    if label_i == pred_i:
                        per_class_correct[label_i] += 1

        acc = correct / max(total, 1)
        print(
            f"epoch {epoch + 1}/{epochs} "
            f"train_loss={running / max(len(train_loader), 1):.4f} "
            f"val_acc={acc:.4f}"
        )
        per_class_parts = []
        for idx, cls_name in enumerate(class_order):
            total_c = int(per_class_total[idx].item())
            if total_c == 0:
                per_class_parts.append(f"{cls_name}=n/a")
            else:
                correct_c = int(per_class_correct[idx].item())
                per_class_parts.append(f"{cls_name}={correct_c / total_c:.3f}")
        print("val_per_class_acc: " + ", ".join(per_class_parts))

        if acc > best_val_acc:
            best_val_acc = acc
            best_epoch = epoch + 1
            best_state_dict = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if early_stopping_patience > 0 and epochs_without_improvement >= early_stopping_patience:
            print(
                f"Early stopping at epoch {epoch + 1}; "
                f"best epoch={best_epoch} best_val_acc={best_val_acc:.4f}"
            )
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)
    save_checkpoint(model, str(output_path))
    print(
        f"Saved best checkpoint to {output_path} "
        f"(best_epoch={best_epoch}, best_val_acc={best_val_acc:.4f})"
    )


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
    use_class_weighted_loss: bool,
    use_weighted_sampling: bool,
    early_stopping_patience: int,
) -> None:
    run_binary_training(
        train_dir=train_dir,
        val_dir=val_dir,
        output_path=output_path,
        epochs=epochs,
        lr=lr,
        batch_size=batch_size,
        num_workers=num_workers,
        freeze_backbone_epochs=freeze_backbone_epochs,
        use_class_weighted_loss=use_class_weighted_loss,
        use_weighted_sampling=use_weighted_sampling,
        early_stopping_patience=early_stopping_patience,
        class_order=BINARY_VERIFIER_CLASS_ORDER,
        model_builder=build_mobilenet_v3_binary_classifier,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transfer-learn MobileNetV3 for binary verifier (yes/no)."
    )
    parser.add_argument(
        "--train_dir",
        type=Path,
        required=True,
        help="Path to a yes/no binary train folder.",
    )
    parser.add_argument(
        "--val_dir",
        type=Path,
        required=True,
        help="Path to a yes/no binary val folder.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ml_service/weights/binary_verifier_mobilenet_v3.pt"),
        help="Output checkpoint path for the binary verifier model.",
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--freeze_backbone_epochs", type=int, default=1)
    parser.add_argument(
        "--weighted_sampling",
        action="store_true",
        help="Use inverse-frequency weighted sampling for the training loader.",
    )
    parser.add_argument(
        "--disable_class_weighted_loss",
        action="store_true",
        help="Disable inverse-frequency class weights in CrossEntropyLoss.",
    )
    parser.add_argument(
        "--early_stopping_patience",
        type=int,
        default=5,
        help="Stop if val_acc does not improve for this many epochs (0 disables).",
    )
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
        use_class_weighted_loss=not args.disable_class_weighted_loss,
        use_weighted_sampling=args.weighted_sampling,
        early_stopping_patience=args.early_stopping_patience,
    )


if __name__ == "__main__":
    main()
