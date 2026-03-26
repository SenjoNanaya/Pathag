from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.schemas.schemas import (
    CombinedImageClassificationResponse,
    ObstacleClassificationResponse,
    ObstacleType,
    PathClassificationResponse,
    PathCondition,
)
from app.services.obstacle_classification import get_obstacle_classifier
from app.services.path_classification import get_path_classifier

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_image_bytes(body: bytes) -> None:
    if not body:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        Image.open(BytesIO(body)).verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid or unreadable image")


@router.post(
    "/classify-image",
    response_model=CombinedImageClassificationResponse,
    summary="Classify sidewalk/path surface and obstacles from one image",
)
async def classify_image(file: UploadFile = File(...)) -> CombinedImageClassificationResponse:
    body = await file.read()
    if len(body) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")

    _validate_image_bytes(body)

    # Path (sidewalk/path surface condition).
    try:
        raw_path = get_path_classifier().predict_proba(body)
    except (OSError, ValueError):
        logger.warning("Path image classification failed (decode or tensor error)")
        raise HTTPException(status_code=400, detail="Could not classify image") from None
    logger.info("Path image classification completed")

    path_resp = PathClassificationResponse(
        path_condition=PathCondition(raw_path["path_condition"]),
        confidence=raw_path["confidence"],
        probabilities=raw_path["probabilities"],
        narrative_reasons=raw_path["narrative_reasons"],
        checkpoint_loaded=raw_path["checkpoint_loaded"],
        eligible_for_live_map=False,
    )

    # Obstacle (obstacle type).
    try:
        raw_obstacle = get_obstacle_classifier().predict_proba(body)
    except (OSError, ValueError):
        logger.warning("Obstacle image classification failed (decode or tensor error)")
        raise HTTPException(status_code=400, detail="Could not classify image") from None
    logger.info("Obstacle image classification completed")

    obstacle_resp: ObstacleClassificationResponse = ObstacleClassificationResponse(
        obstacle_type=ObstacleType(raw_obstacle["obstacle_type"]),
        confidence=raw_obstacle["confidence"],
        probabilities=raw_obstacle["probabilities"],
        narrative_reasons=raw_obstacle["narrative_reasons"],
        checkpoint_loaded=raw_obstacle["checkpoint_loaded"],
        eligible_for_live_map=False,
    )

    # "If there are any": treat the `other` bucket as "no clear obstacle".
    obstacle_present = obstacle_resp.obstacle_type != ObstacleType.OTHER

    return CombinedImageClassificationResponse(
        path=path_resp,
        obstacle_present=obstacle_present,
        obstacle=obstacle_resp if obstacle_present else None,
    )

