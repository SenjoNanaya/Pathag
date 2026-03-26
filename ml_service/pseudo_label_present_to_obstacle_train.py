from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from collections import Counter
from pathlib import Path

from tqdm import tqdm

from ml_service.obstacle_inference import ObstacleImageClassifier
from ml_service.obstacle_labels import OBSTACLE_TYPE_CLASS_ORDER

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".ppm",
    ".bmp",
    ".pgm",
    ".tif",
    ".tiff",
    ".webp",
}


def _is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def _iter_images(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*") if _is_supported_image(p)])


def _unique_output_path(dst_dir: Path, src_path: Path) -> Path:
    digest = hashlib.sha1(str(src_path).encode("utf-8")).hexdigest()[:10]
    return dst_dir / f"{src_path.stem}_{digest}{src_path.suffix.lower()}"


def _write_manifest_csv(manifest_path: Path, rows: list[tuple[str, str]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filepath", "label"])
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Pseudo-label binary 'yes' images into binary obstacle_dataset/train "
            "using the current obstacle classifier and a confidence threshold."
        )
    )
    parser.add_argument(
        "--yes_dir",
        type=Path,
        default=Path("obstacle_verifier_dataset/train/yes"),
        help="Directory containing images labeled as 'yes'.",
    )
    parser.add_argument(
        "--present_dir",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--output_train_dir",
        type=Path,
        default=Path("obstacle_dataset/train"),
        help="Binary ImageFolder train directory (yes/no) for pseudo-labeled images.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("ml_service/weights/obstacle_mobilenet_v3.pt"),
        help="Path to binary obstacle classifier checkpoint.",
    )
    parser.add_argument(
        "--confidence_threshold",
        type=float,
        default=0.85,
        help="Keep predictions with confidence >= this value.",
    )
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument(
        "--copy_mode",
        choices=["copy", "move"],
        default="copy",
        help="Whether to copy or move accepted images to output directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap on number of images to process (0 means no cap).",
    )
    parser.add_argument(
        "--manifest_path",
        type=Path,
        default=None,
        help=(
            "CSV output for exported pseudo-labels (columns: filepath,label). "
            "Defaults to <output_train_dir>/labels.csv."
        ),
    )
    args = parser.parse_args()

    input_yes_dir = args.present_dir or args.yes_dir
    if not input_yes_dir.exists():
        raise SystemExit(f"yes_dir does not exist: {input_yes_dir}")
    if not args.output_train_dir.exists():
        raise SystemExit(f"output_train_dir does not exist: {args.output_train_dir}")
    if not args.checkpoint.exists():
        raise SystemExit(f"checkpoint does not exist: {args.checkpoint}")
    if not (0.0 <= args.confidence_threshold <= 1.0):
        raise SystemExit("confidence_threshold must be between 0.0 and 1.0")

    required_classes = set(OBSTACLE_TYPE_CLASS_ORDER)
    found_classes = {p.name for p in args.output_train_dir.iterdir() if p.is_dir()}
    missing = sorted(required_classes - found_classes)
    if missing:
        raise SystemExit(
            "output_train_dir is missing class folders:\n"
            f"{missing}\n"
            f"Required: {sorted(required_classes)}"
        )

    images = _iter_images(input_yes_dir)
    if args.limit > 0:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"No supported image files found under: {input_yes_dir}")

    classifier = ObstacleImageClassifier(
        device=args.device,
        checkpoint_path=str(args.checkpoint.resolve()),
    )

    accepted = 0
    skipped_low_conf = 0
    failed = 0
    class_counts: Counter[str] = Counter()
    manifest_rows: list[tuple[str, str]] = []

    for image_path in tqdm(images, desc="Pseudo-labeling"):
        try:
            image_bytes = image_path.read_bytes()
            pred = classifier.predict_proba(image_bytes)
        except Exception:
            failed += 1
            continue

        predicted_class = str(pred["obstacle_type"])
        confidence = float(pred["confidence"])
        if confidence < args.confidence_threshold:
            skipped_low_conf += 1
            continue

        dst_class_dir = args.output_train_dir / predicted_class
        dst_class_dir.mkdir(parents=True, exist_ok=True)
        dst_path = _unique_output_path(dst_class_dir, image_path)

        if args.copy_mode == "move":
            shutil.move(str(image_path), str(dst_path))
        else:
            shutil.copy2(str(image_path), str(dst_path))

        accepted += 1
        class_counts[predicted_class] += 1
        manifest_rows.append((str(dst_path.resolve()), predicted_class))

    manifest_path = args.manifest_path or (args.output_train_dir / "labels.csv")
    _write_manifest_csv(manifest_path, manifest_rows)

    print("Pseudo-labeling complete.")
    print(f"processed={len(images)}")
    print(f"accepted={accepted}")
    print(f"skipped_low_confidence={skipped_low_conf}")
    print(f"failed={failed}")
    print(f"labels_manifest={manifest_path}")
    print("accepted_per_class:")
    for cls in OBSTACLE_TYPE_CLASS_ORDER:
        print(f"  {cls}: {class_counts.get(cls, 0)}")


if __name__ == "__main__":
    main()

