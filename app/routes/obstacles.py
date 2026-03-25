from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from app.config import settings
from app.database import get_db
from app.models.models import (
    ObstacleReport,
    ObstacleType,
    ObstacleVerification,
)
from app.schemas.schemas import (
    ObstacleReportCreate,
    ObstacleReportResponse,
    ObstacleResolveCreate,
    ObstacleVerificationCreate,
    ObstacleClassificationResponse,
)
from app.services.obstacle_classification import get_obstacle_classifier

logger = logging.getLogger(__name__)

router = APIRouter()


def _wkt_point(longitude: float, latitude: float) -> WKTElement:
    # geoalchemy2 expects WKTElement for geometry columns.
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


@router.post(
    "/obstacles/reports",
    response_model=ObstacleReportResponse,
    summary="Create an obstacle report (unverified by default).",
)
def create_obstacle_report(
    payload: ObstacleReportCreate,
    db: Session = Depends(get_db),
) -> ObstacleReportResponse:
    report = ObstacleReport(
        location=_wkt_point(payload.longitude, payload.latitude),
        latitude=payload.latitude,
        longitude=payload.longitude,
        obstacle_type=payload.obstacle_type,
        description=payload.description,
        severity=payload.severity,
        is_temporary=payload.is_temporary,
        image_url=None,
        is_verified=False,
        is_resolved=False,
        reporter_id=payload.reporter_id,
    )

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post(
    "/obstacles/reports/{report_id}/verify",
    response_model=ObstacleReportResponse,
    summary="Submit a human verification for an obstacle report.",
)
def verify_obstacle_report(
    report_id: int,
    payload: ObstacleVerificationCreate,
    db: Session = Depends(get_db),
) -> ObstacleReportResponse:
    report = db.query(ObstacleReport).filter(ObstacleReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Obstacle report not found")

    # Record the verification event.
    verification = ObstacleVerification(
        obstacle_report_id=report.id,
        verifier_id=payload.verifier_id,
        notes=payload.notes,
    )
    db.add(verification)
    db.commit()

    # Compute how many independent confirmations exist and set `is_verified`.
    verification_count = (
        db.query(ObstacleVerification)
        .filter(ObstacleVerification.obstacle_report_id == report.id)
        .count()
    )

    report.is_verified = verification_count >= settings.OBSTACLE_VERIFICATION_THRESHOLD
    db.commit()
    db.refresh(report)

    return report


@router.post(
    "/obstacles/reports/{report_id}/resolve",
    response_model=ObstacleReportResponse,
    summary="Mark an obstacle report as resolved/inactive.",
)
def resolve_obstacle_report(
    report_id: int,
    payload: ObstacleResolveCreate,
    db: Session = Depends(get_db),
) -> ObstacleReportResponse:
    # NOTE: this prototype resolves without auditing resolver_id in a separate table.
    report = db.query(ObstacleReport).filter(ObstacleReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Obstacle report not found")

    report.is_resolved = True
    report.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report


@router.websocket("/realtime/obstacles/stream")
async def realtime_obstacle_stream(websocket: WebSocket) -> None:
    """
    Minimal real-time obstacle detection.

    Client sends JSON messages:
      {
        "image_base64": "<base64 encoded JPEG/PNG>",
        "latitude": <float>,
        "longitude": <float>
      }

    Server replies with classifier output + a suggested severity (1..5).

    This endpoint does NOT write to the DB; reports are created via the HTTP
    endpoints so they can go through verification/moderation.
    """

    await websocket.accept()
    classifier = get_obstacle_classifier()

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            image_b64 = data.get("image_base64")
            if not image_b64:
                await websocket.send_text(json.dumps({"error": "Missing image_base64"}))
                continue

            try:
                image_bytes = base64.b64decode(image_b64, validate=True)
            except Exception:
                await websocket.send_text(json.dumps({"error": "Invalid base64 image"}))
                continue

            raw = classifier.predict_proba(image_bytes)

            # Suggested severity: map confidence to 1..5 (simple heuristic).
            confidence = float(raw["confidence"])
            suggested_severity = max(1, min(5, int(round(confidence * 5))))

            response: dict[str, object] = {
                "obstacle_type": raw["obstacle_type"],
                "confidence": confidence,
                "probabilities": raw["probabilities"],
                "narrative_reasons": raw["narrative_reasons"],
                "checkpoint_loaded": raw["checkpoint_loaded"],
                "eligible_for_live_map": False,  # requires verification flow
                "suggested_severity": suggested_severity,
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
            }
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        return

