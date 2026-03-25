from __future__ import annotations

import argparse
import json
import random
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from datasets import load_dataset
from PIL import Image
from tqdm import tqdm

from ml_service.labels import PATH_CONDITION_CLASS_ORDER, project_sidewalk_label_hints
from ml_service.labels import class_index_for_label as _class_index_for_label


def _row_to_text_blob(row: Dict[str, Any]) -> str:
    row_wo_image = {k: v for k, v in row.items() if k != "image"}
    try:
        return json.dumps(row_wo_image, default=str).lower()
    except TypeError:
        return str(row_wo_image).lower()


def _infer_path_label(text_blob: str) -> Optional[str]:
    """
    Best-effort heuristic mapping from Project Sidewalk-style tags to your
    `PathCondition` buckets.
    """

    rules: list[tuple[str, list[str]]] = []
    for label, hints in project_sidewalk_label_hints.items():
        rules.append((label, [h.lower() for h in hints]))

    for label, needles in rules:
        if any(n in text_blob for n in needles):
            return label

    return None


def _save_image_any(image_val: Any, out_path: Path) -> None:
    if isinstance(image_val, Image.Image):
        image_val.save(out_path)
        return

    if isinstance(image_val, bytes):
        img = Image.open(BytesIO(image_val)).convert("RGB")
        img.save(out_path)
        return

    if isinstance(image_val, dict):
        for k in ["bytes", "data"]:
            if k in image_val and isinstance(image_val[k], (bytes, bytearray)):
                img = Image.open(BytesIO(image_val[k])).convert("RGB")
                img.save(out_path)
                return

    raise ValueError(f"Unsupported image value type: {type(image_val)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Project Sidewalk dataset to an ImageFolder path-condition dataset."
    )
    parser.add_argument("--hf_dataset", default="projectsidewalk/sidewalk-tagger-ai-validated")
    parser.add_argument("--split", default="train")
    parser.add_argument("--output_dir", required=True, help="e.g. path_dataset")
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

    valid = set(PATH_CONDITION_CLASS_ORDER)

    i = 0
    for row in tqdm(ds, total=min(len(ds), args.max_samples)):
        if i >= args.max_samples:
            break

        if "image" not in row:
            raise SystemExit("Expected an `image` column in the dataset row.")

        text_blob = _row_to_text_blob(row)
        label = _infer_path_label(text_blob)
        if not label or label not in valid:
            continue

        # Sanity-check mapping works with your MobileNetV3 head order.
        _ = _class_index_for_label(label)

        split_dir = val_dir if rng.random() < args.val_ratio else train_dir
        label_dir = split_dir / label
        label_dir.mkdir(parents=True, exist_ok=True)

        out_path = label_dir / f"{i:06d}.jpg"
        _save_image_any(row["image"], out_path)
        i += 1

    print(f"Done. Wrote up to {i} samples into {out_dir}.")


if __name__ == "__main__":
    main()

