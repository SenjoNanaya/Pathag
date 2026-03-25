"""
Path condition image classification API.

Responses are explanatory (softmax + narrative_reasons) and never auto-write to the map:
community or CV-derived updates must pass human verification before affecting live scores.
"""

from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.schemas.schemas import PathClassificationResponse, PathCondition
from app.services.path_classification import get_path_classifier

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/classify-path-image",
    response_model=PathClassificationResponse,
    summary="Classify sidewalk/path surface from an image (MobileNetV3 transfer learning)",
)
async def classify_path_image(file: UploadFile = File(...)) -> PathClassificationResponse:
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
        raw = get_path_classifier().predict_proba(body)
    except (OSError, ValueError):
        logger.warning("Path image classification failed (decode or tensor error)")
        raise HTTPException(
            status_code=400,
            detail="Could not classify image",
        ) from None

    # Do not log upload filenames or user identifiers alongside image payloads (privacy).
    logger.info("Path image classification completed")

    return PathClassificationResponse(
        path_condition=PathCondition(raw["path_condition"]),
        confidence=raw["confidence"],
        probabilities=raw["probabilities"],
        narrative_reasons=raw["narrative_reasons"],
        checkpoint_loaded=raw["checkpoint_loaded"],
        eligible_for_live_map=False,
    )
