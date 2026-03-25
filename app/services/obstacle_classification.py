from __future__ import annotations

from pathlib import Path
from typing import Optional

from ml_service.obstacle_inference import ObstacleImageClassifier

_classifier: Optional[ObstacleImageClassifier] = None


def _resolve_checkpoint_path(configured_path: Optional[str]) -> Optional[str]:
    project_root = Path(__file__).resolve().parents[2]
    default_rel = Path("ml_service/weights/obstacle_mobilenet_v3.pt")

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


def get_obstacle_classifier() -> ObstacleImageClassifier:
    """
    Lazily load obstacle-type classifier (runs independently of path condition).
    """
    global _classifier
    if _classifier is None:
        from app.config import settings

        checkpoint_path = _resolve_checkpoint_path(settings.OBSTACLE_ML_CHECKPOINT_PATH)
        _classifier = ObstacleImageClassifier(
            device=settings.ML_DEVICE,
            checkpoint_path=checkpoint_path,
        )
    return _classifier


def reset_obstacle_classifier_for_tests() -> None:
    """Test hook only."""
    global _classifier
    _classifier = None

