from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

OLD_NINE_CLASS_LABELS = (
    "vendor_stall",
    "parked_vehicle",
    "construction",
    "broken_pavement",
    "flooding",
    "steep_incline",
    "stairs",
    "no_curb_cut",
    "other",
)

BINARY_LABELS = ("yes", "no")


def _existing_class_dirs(split_dir: Path) -> set[str]:
    if not split_dir.exists():
        return set()
    return {p.name for p in split_dir.iterdir() if p.is_dir()}


def _move_if_exists(src: Path, dst_root: Path) -> bool:
    if not src.exists():
        return False
    dst_root.mkdir(parents=True, exist_ok=True)
    dst = dst_root / src.name
    i = 1
    while dst.exists():
        dst = dst_root / f"{src.name}_{i}"
        i += 1
    shutil.move(str(src), str(dst))
    return True


def _remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "One-time migration utility: archive/remove old 9-class obstacle dataset folders "
            "before regenerating binary yes/no data."
        )
    )
    parser.add_argument("--dataset_root", type=Path, default=Path("obstacle_dataset"))
    parser.add_argument(
        "--archive_root",
        type=Path,
        default=Path("obstacle_dataset/_migration_archive"),
        help="Where old folders are moved (archive mode).",
    )
    parser.add_argument(
        "--mode",
        choices=("archive", "delete"),
        default="archive",
        help="archive: move old folders to archive_root; delete: permanently remove them.",
    )
    args = parser.parse_args()

    dataset_root = args.dataset_root
    if not dataset_root.exists():
        raise SystemExit(f"dataset_root does not exist: {dataset_root}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_session_root = args.archive_root / timestamp

    moved_or_deleted = 0
    found_binary = 0

    for split in ("train", "val"):
        split_dir = dataset_root / split
        existing = _existing_class_dirs(split_dir)
        if not existing:
            continue

        if any(lbl in existing for lbl in BINARY_LABELS):
            found_binary += 1

        for old_label in OLD_NINE_CLASS_LABELS:
            old_dir = split_dir / old_label
            if args.mode == "archive":
                changed = _move_if_exists(old_dir, archive_session_root / split)
            else:
                changed = _remove_if_exists(old_dir)
            if changed:
                moved_or_deleted += 1

    # Recreate split + binary class dirs so regeneration has expected structure.
    for split in ("train", "val"):
        split_dir = dataset_root / split
        split_dir.mkdir(parents=True, exist_ok=True)
        for cls in BINARY_LABELS:
            (split_dir / cls).mkdir(parents=True, exist_ok=True)

    print("Migration completed.")
    print(f"mode={args.mode}")
    print(f"dataset_root={dataset_root}")
    print(f"old_class_dirs_changed={moved_or_deleted}")
    print(f"splits_with_existing_binary_dirs={found_binary}")
    if args.mode == "archive":
        print(f"archive_session_root={archive_session_root}")
    print("ready_for_binary_regeneration=yes")


if __name__ == "__main__":
    main()

