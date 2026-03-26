"""
Binary verifier class order.

Important: keep "yes" at index 1 for compatibility with existing
verifier checkpoints trained with legacy (absent/present) ordering.

Index 0: no
Index 1: yes
"""

from typing import Tuple

BINARY_VERIFIER_CLASS_ORDER: Tuple[str, str] = ("no", "yes")

