"""
Pathag ML service: MobileNetV3 transfer learning for sidewalk / path condition classification.

Aligned with Project Sidewalk-style surface labels mapped to PathCondition.
"""

from .labels import PATH_CONDITION_CLASS_ORDER, project_sidewalk_label_hints

__all__ = [
    "PATH_CONDITION_CLASS_ORDER",
    "project_sidewalk_label_hints",
]
