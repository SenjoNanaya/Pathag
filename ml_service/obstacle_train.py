from __future__ import annotations

import argparse
from pathlib import Path
from ml_service.binary_verifier_train import run_binary_training
from ml_service.model import build_mobilenet_v3_obstacle_classifier
from ml_service.obstacle_labels import OBSTACLE_TYPE_CLASS_ORDER


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
        class_order=OBSTACLE_TYPE_CLASS_ORDER,
        model_builder=build_mobilenet_v3_obstacle_classifier,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Transfer-learn MobileNetV3 for obstacle types.")
    parser.add_argument(
        "--train_dir",
        type=Path,
        required=True,
        help="Path to obstacle_dataset/train",
    )
    parser.add_argument(
        "--val_dir",
        type=Path,
        required=True,
        help="Path to obstacle_dataset/val",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ml_service/weights/obstacle_mobilenet_v3.pt"),
        help="Output checkpoint path (do not overwrite path-condition weights)",
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

