from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.schemas.schemas import ObstacleClassificationResponse, ObstacleType
from app.services.obstacle_classification import get_obstacle_classifier

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/classify-obstacle-image",
    response_model=ObstacleClassificationResponse,
    summary="Classify obstacle type from an image (runs regardless of path condition)",
)
async def classify_obstacle_image(
    file: UploadFile = File(...),
) -> ObstacleClassificationResponse:
    body = await file.read()
    if len(body) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")
    if not body:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        Image.open(BytesIO(body)).verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid or unreadable image")

    try:
        raw = get_obstacle_classifier().predict_proba(body)
    except (OSError, ValueError):
        logger.warning("Obstacle image classification failed (decode or tensor error)")
        raise HTTPException(
            status_code=400,
            detail="Could not classify image",
        ) from None

    logger.info("Obstacle image classification completed")

    return ObstacleClassificationResponse(
        obstacle_type=ObstacleType(raw["obstacle_type"]),
        confidence=raw["confidence"],
        probabilities=raw["probabilities"],
        narrative_reasons=raw["narrative_reasons"],
        checkpoint_loaded=raw["checkpoint_loaded"],
        eligible_for_live_map=False,
    )

