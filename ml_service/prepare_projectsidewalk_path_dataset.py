from __future__ import annotations

import argparse
import random
from io import BytesIO
from pathlib import Path
from typing import Any

from datasets import load_dataset
from PIL import Image
from tqdm import tqdm


def _save_image_any(image_val: Any, out_path: Path) -> None:
    if isinstance(image_val, Image.Image):
        image_val.save(out_path)
        return
    if isinstance(image_val, bytes):
        img = Image.open(BytesIO(image_val)).convert("RGB")
        img.save(out_path)
        return
    if isinstance(image_val, dict):
        for key in ("bytes", "data"):
            if key in image_val and isinstance(image_val[key], (bytes, bytearray)):
                img = Image.open(BytesIO(image_val[key])).convert("RGB")
                img.save(out_path)
                return
    raise ValueError(f"Unsupported image value type: {type(image_val)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a binary surface-problem verifier dataset (present/absent) "
            "from Project Sidewalk surface-problem validator data."
        )
    )
    parser.add_argument(
        "--hf_dataset",
        default="projectsidewalk/sidewalk-validator-ai-dataset-surfaceproblem",
    )
    parser.add_argument("--split", default="train")
    parser.add_argument("--output_dir", required=True, help="e.g. surface_problem_verifier_dataset")
    parser.add_argument("--max_samples", type=int, default=20000)
    parser.add_argument("--val_ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    train_dir = out_dir / "train"
    val_dir = out_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    ds = load_dataset(args.hf_dataset, split=args.split)

    i = 0
    for row in tqdm(ds, total=min(len(ds), args.max_samples)):
        if i >= args.max_samples:
            break

        if "image" not in row or "label" not in row:
            raise SystemExit("Expected columns: image, label")

        bucket = "present" if int(row["label"]) == 0 else "absent"

        split_dir = val_dir if rng.random() < args.val_ratio else train_dir
        label_dir = split_dir / bucket
        label_dir.mkdir(parents=True, exist_ok=True)

        out_path = label_dir / f"{i:06d}.jpg"
        _save_image_any(row["image"], out_path)
        i += 1

    print(f"Done. Wrote up to {i} samples into {out_dir}.")


if __name__ == "__main__":
    main()

