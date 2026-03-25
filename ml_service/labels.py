"""
Class order and Project Sidewalk–style label mapping.

Project Sidewalk uses mission-centric labels (e.g. surface problems, obstacles).
For training data, map exported or curated tags into these PathCondition buckets
using folder names (ImageFolder) matching the string values below.
"""

from typing import Dict, List, Tuple

# Fixed index order must match model output logits and training folders.
PATH_CONDITION_CLASS_ORDER: Tuple[str, ...] = (
    "smooth",
    "cracked",
    "uneven",
    "obstructed",
    "no_sidewalk",
    "under_construction",
)


def class_index_for_label(label: str) -> int:
    normalized = label.strip().lower().replace(" ", "_")
    if normalized not in PATH_CONDITION_CLASS_ORDER:
        raise ValueError(
            f"Unknown path condition label {label!r}; "
            f"expected one of {PATH_CONDITION_CLASS_ORDER}"
        )
    return PATH_CONDITION_CLASS_ORDER.index(normalized)


# Hints for mapping raw Project Sidewalk–style tags to our buckets (documentation only).
project_sidewalk_label_hints: Dict[str, List[str]] = {
    "smooth": ["surface problem absent", "no surface problem", "clean", "maintained"],
    "cracked": ["cracks", "cracked", "broken surface", "deteriorated"],
    "uneven": ["uneven", "grass", "gravel", "dirt"],
    "obstructed": ["obstacle", "object in path", "debris", "parked object"],
    "no_sidewalk": ["no sidewalk", "missing sidewalk", "road edge"],
    "under_construction": ["construction", "work zone", "temporary closure"],
}
