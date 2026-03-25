from __future__ import annotations

import argparse
import json
import os
import random
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from datasets import load_dataset
from PIL import Image
from tqdm import tqdm

from ml_service.obstacle_labels import OBSTACLE_TYPE_CLASS_ORDER
from app.schemas.schemas import ObstacleType


def _row_to_text_blob(row: Dict[str, Any]) -> str:
    # Avoid serializing the image payload (it can be large).
    row_wo_image = {k: v for k, v in row.items() if k != "image"}
    try:
        return json.dumps(row_wo_image, default=str).lower()
    except TypeError:
        return str(row_wo_image).lower()


def _infer_obstacle_label(text_blob: str) -> Optional[ObstacleType]:
    """
    Best-effort heuristic mapping from Project Sidewalk-style tags to your
    `ObstacleType` classes.

    You should refine these once you confirm the dataset's exact fields/tags.
    """

    # The first match wins.
    rules: list[tuple[ObstacleType, list[str]]] = [
        (ObstacleType.NO_CURB_CUT, ["no curbramp", "no curbramp", "no curbramp", "no-curbramp", "curbramp"]),
        (ObstacleType.FLOODING, ["pooled-water", "pooled water", "pooled-water", "flood", "standing water", "water"]),
        (ObstacleType.STEEP_INCLINE, ["steep", "slope", "incline"]),
        (ObstacleType.CONSTRUCTION, ["construction", "work zone", "temporary closure", "work-area"]),
        (ObstacleType.STAIRS, ["stairs", "steps", "stair"]),
        (ObstacleType.BROKEN_PAVEMENT, ["surface-problem", "surface problem", "broken pavement", "cracked", "deteriorated", "uneven"]),
        (ObstacleType.VENDOR_STALL, ["vendor", "stall", "market stall"]),
        (ObstacleType.PARKED_VEHICLE, ["parked", "vehicle", "car", "truck"]),
    ]

    for label, needles in rules:
        if any(n in text_blob for n in needles):
            return label

    # If we can't tell which bucket, map to "other" to keep usable training data.
    return ObstacleType.OTHER


def _save_image_any(image_val: Any, out_path: Path) -> None:
    # HF image columns often return PIL.Image directly.
    if isinstance(image_val, Image.Image):
        image_val.save(out_path)
        return

    if isinstance(image_val, bytes):
        img = Image.open(BytesIO(image_val)).convert("RGB")
        img.save(out_path)
        return

    # Some datasets return dict-like objects.
    if isinstance(image_val, dict):
        # Try common keys.
        for k in ["bytes", "data"]:
            if k in image_val and isinstance(image_val[k], (bytes, bytearray)):
                img = Image.open(BytesIO(image_val[k])).convert("RGB")
                img.save(out_path)
                return

    raise ValueError(f"Unsupported image value type: {type(image_val)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Project Sidewalk dataset to an ImageFolder obstacle dataset."
    )
    parser.add_argument("--hf_dataset", default="projectsidewalk/sidewalk-tagger-ai-validated")
    parser.add_argument("--split", default="train")
    parser.add_argument("--output_dir", required=True, help="e.g. obstacle_dataset")
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
    allowed = set(ObstacleType(v) for v in OBSTACLE_TYPE_CLASS_ORDER)

    i = 0
    for row in tqdm(ds, total=min(len(ds), args.max_samples)):
        if i >= args.max_samples:
            break

        if "image" not in row:
            raise SystemExit("Expected an `image` column in the dataset row.")

        text_blob = _row_to_text_blob(row)
        label = _infer_obstacle_label(text_blob)
        if label is None or label not in allowed:
            continue

        split_dir = val_dir if rng.random() < args.val_ratio else train_dir
        label_dir = split_dir / label.value
        label_dir.mkdir(parents=True, exist_ok=True)

        out_path = label_dir / f"{i:06d}.jpg"
        _save_image_any(row["image"], out_path)

        i += 1

    print(f"Done. Wrote up to {i} samples into {out_dir}.")


if __name__ == "__main__":
    main()

