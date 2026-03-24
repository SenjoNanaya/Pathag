"""
Singleton accessor for the path-image classifier (MobileNetV3).

Loads once per process; configuration comes from app.config (adjustable device and checkpoint).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ml_service.inference import PathImageClassifier

_classifier: Optional[PathImageClassifier] = None


def _resolve_checkpoint_path(configured_path: Optional[str]) -> Optional[str]:
    """
    Resolve checkpoint path robustly for either launch directory:
    - Hackathon root
    - Pathag project root
    """
    project_root = Path(__file__).resolve().parents[2]
    default_rel = Path("ml_service/weights/path_mobilenet_v3.pt")

    candidates: list[Path] = []
    if configured_path:
        configured = Path(configured_path)
        if configured.is_absolute():
            candidates.append(configured)
        else:
            candidates.extend([Path.cwd() / configured, project_root / configured])
    else:
        candidates.extend([project_root / default_rel, Path.cwd() / default_rel])

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return None


def get_path_classifier() -> PathImageClassifier:
    global _classifier
    if _classifier is None:
        from app.config import settings
        checkpoint_path = _resolve_checkpoint_path(settings.ML_CHECKPOINT_PATH)

        _classifier = PathImageClassifier(
            device=settings.ML_DEVICE,
            checkpoint_path=checkpoint_path,
        )
    return _classifier


def reset_path_classifier_for_tests() -> None:
    """Test hook only."""
    global _classifier
    _classifier = None
