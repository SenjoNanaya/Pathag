"""
Obstacle-type class order for obstacle image classification.

The fixed index order must match:
- the training ImageFolder labels (if used)
- the classifier head output logits order
- the inference-time mapping from probabilities to class names
"""

from typing import Tuple


OBSTACLE_TYPE_CLASS_ORDER: Tuple[str, ...] = (
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

