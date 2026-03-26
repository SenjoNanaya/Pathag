from __future__ import annotations

from pathlib import Path
from typing import Optional

from ml_service.binary_verifier_inference import BinaryImageVerifier

_obstruction_verifier: Optional[BinaryImageVerifier] = None
_surface_problem_verifier: Optional[BinaryImageVerifier] = None


def _resolve_checkpoint_path(configured_path: Optional[str], default_rel: str) -> Optional[str]:
    project_root = Path(__file__).resolve().parents[2]
    default_rel_path = Path(default_rel)

    candidates: list[Path] = []
    if configured_path:
        configured = Path(configured_path)
        if configured.is_absolute():
            candidates.append(configured)
        else:
            candidates.extend([Path.cwd() / configured, project_root / configured])
    else:
        candidates.extend([project_root / default_rel_path, Path.cwd() / default_rel_path])

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return None


def get_obstruction_verifier() -> BinaryImageVerifier:
    global _obstruction_verifier
    if _obstruction_verifier is None:
        from app.config import settings

        checkpoint_path = _resolve_checkpoint_path(
            settings.OBSTRUCTION_VERIFIER_ML_CHECKPOINT_PATH,
            "ml_service/weights/obstruction_verifier_mobilenet_v3.pt",
        )
        _obstruction_verifier = BinaryImageVerifier(
            device=settings.ML_DEVICE,
            checkpoint_path=checkpoint_path,
        )
    return _obstruction_verifier


def get_surface_problem_verifier() -> BinaryImageVerifier:
    global _surface_problem_verifier
    if _surface_problem_verifier is None:
        from app.config import settings

        checkpoint_path = _resolve_checkpoint_path(
            settings.SURFACE_PROBLEM_VERIFIER_ML_CHECKPOINT_PATH,
            "ml_service/weights/surface_problem_verifier_mobilenet_v3.pt",
        )
        _surface_problem_verifier = BinaryImageVerifier(
            device=settings.ML_DEVICE,
            checkpoint_path=checkpoint_path,
        )
    return _surface_problem_verifier


def reset_verifiers_for_tests() -> None:
    global _obstruction_verifier, _surface_problem_verifier
    _obstruction_verifier = None
    _surface_problem_verifier = None

