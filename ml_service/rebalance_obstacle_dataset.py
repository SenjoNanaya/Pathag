from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

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


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def _list_images(class_dir: Path) -> list[Path]:
    return sorted([p for p in class_dir.rglob("*") if _is_image(p)])


def _ensure_class_dirs(root: Path) -> None:
    for cls in OBSTACLE_TYPE_CLASS_ORDER:
        (root / cls).mkdir(parents=True, exist_ok=True)


def _copy_with_suffix(src: Path, dst_dir: Path, suffix: str) -> Path:
    base = src.stem
    ext = src.suffix.lower()
    out = dst_dir / f"{base}{suffix}{ext}"
    i = 1
    while out.exists():
        out = dst_dir / f"{base}{suffix}_{i}{ext}"
        i += 1
    shutil.copy2(src, out)
    return out


def _move_to_archive(path: Path, archive_root: Path, dataset_root: Path) -> Path:
    rel = path.relative_to(dataset_root)
    dst = archive_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dst))
    return dst


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebalance binary obstacle_dataset (yes/no): cap dominant class, "
            "enforce validation minimum, and oversample minority class."
        )
    )
    parser.add_argument("--dataset_root", type=Path, default=Path("obstacle_dataset"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--yes_cap", type=int, default=1200)
    parser.add_argument("--val_min_per_class", type=int, default=50)
    parser.add_argument("--minority_target", type=int, default=900)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    dataset_root = args.dataset_root
    train_root = dataset_root / "train"
    val_root = dataset_root / "val"
    archive_root = dataset_root / "_rebalance_archive"

    if not train_root.exists() or not val_root.exists():
        raise SystemExit("dataset_root must contain train/ and val/ folders.")
    _ensure_class_dirs(train_root)
    _ensure_class_dirs(val_root)
    _ensure_class_dirs(archive_root / "train")
    _ensure_class_dirs(archive_root / "val")

    print("Step 1/3: Downsample dominant 'yes' class.")
    yes_dir = train_root / "yes"
    yes_images = _list_images(yes_dir)
    if len(yes_images) > args.yes_cap:
        to_remove = len(yes_images) - args.yes_cap
        candidates = yes_images[:]
        rng.shuffle(candidates)
        for img in candidates[:to_remove]:
            _move_to_archive(img, archive_root / "train", dataset_root)
        print(f"  moved_to_archive={to_remove}")
    else:
        print("  yes class already below cap.")

    print("Step 2/3: Ensure val minimum per class.")
    moved_to_val = 0
    for cls in OBSTACLE_TYPE_CLASS_ORDER:
        val_dir = val_root / cls
        train_dir = train_root / cls
        val_images = _list_images(val_dir)
        if len(val_images) >= args.val_min_per_class:
            continue
        need = args.val_min_per_class - len(val_images)
        train_images = _list_images(train_dir)
        if not train_images:
            continue
        rng.shuffle(train_images)
        for img in train_images[: min(need, len(train_images))]:
            dst = val_dir / img.name
            i = 1
            while dst.exists():
                dst = val_dir / f"{img.stem}_{i}{img.suffix.lower()}"
                i += 1
            shutil.move(str(img), str(dst))
            moved_to_val += 1
    print(f"  moved_train_to_val={moved_to_val}")

    print("Step 3/3: Boost minority class by oversampling.")
    oversampled = 0
    yes_count = len(_list_images(train_root / "yes"))
    no_count = len(_list_images(train_root / "no"))
    minority_class = "yes" if yes_count < no_count else "no"
    class_dir = train_root / minority_class
    images = _list_images(class_dir)
    target = max(args.minority_target, min(yes_count, no_count))
    while images and len(images) < target:
        src = rng.choice(images)
        _copy_with_suffix(src, class_dir, "_oversample")
        images = _list_images(class_dir)
        oversampled += 1
    print(f"  oversampled_copies_added={oversampled}")

    print("Rebalance completed.")
    for split_root, split_name in ((train_root, "train"), (val_root, "val")):
        print(f"[{split_name}]")
        total = 0
        for cls in OBSTACLE_TYPE_CLASS_ORDER:
            c = len(_list_images(split_root / cls))
            total += c
            print(f"  {cls}: {c}")
        print(f"  total: {total}")


if __name__ == "__main__":
    main()

