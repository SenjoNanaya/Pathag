from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from app.config import settings
from app.database import get_db
from app.models.models import (
    ObstacleSubtype,
    ObstacleReport,
    SubtypeSource,
    ObstacleType,
    ObstacleVerification,
    User,
)
from app.schemas.schemas import (
    ObstacleVerificationTemplate,
    ObstacleResolveTemplate,
    ObstacleReportCreate,
    ObstacleReportResponse,
    AdminObstacleReportResponse,
    ObstacleResolveCreate,
    ObstacleVerificationCreate,
    ObstacleClassificationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
REPORT_UPLOAD_DIR = Path(settings.UPLOAD_DIR) / "reports"
REPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _suggest_report_subtype(
    *,
    suggested_report_kind: str,
    obstacle_type: str,
) -> Optional[str]:
    # Lightweight defaults until a dedicated subtype model is available.
    if suggested_report_kind == "surface_problem":
        return ObstacleSubtype.BROKEN_PAVEMENT.value
    if suggested_report_kind == "obstacle" and obstacle_type == ObstacleType.YES.value:
        return ObstacleSubtype.PARKED_VEHICLE.value
    return None


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
    reporter_id = payload.reporter_id
    # Swagger/UI sometimes submits `0` for "empty" numeric fields.
    if reporter_id == 0:
        reporter_id = None

    if reporter_id is not None:
        exists = db.query(User.id).filter(User.id == reporter_id).first()
        if exists is None:
            raise HTTPException(
                status_code=400,
                detail=f"reporter_id={reporter_id} does not exist in users.",
            )

    report = ObstacleReport(
        location=_wkt_point(payload.longitude, payload.latitude),
        latitude=payload.latitude,
        longitude=payload.longitude,
        obstacle_type=payload.obstacle_type,
        report_kind=payload.report_kind,
        report_subtype=payload.report_subtype,
        subtype_source=payload.subtype_source,
        description=payload.description,
        severity=payload.severity,
        is_temporary=payload.is_temporary,
        image_url=None,
        is_verified=False,
        is_resolved=False,
        reporter_id=reporter_id,
    )

    db.add(report)
    try:
        db.commit()
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid report enum value(s). Check report_kind/report_subtype/subtype_source.",
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid report payload or foreign-key reference.",
        ) from None
    db.refresh(report)
    return report


@router.get(
    "/obstacles/reports",
    response_model=list[AdminObstacleReportResponse],
    summary="Admin list of obstacle reports with filters and verification counts.",
)
def list_obstacle_reports(
    db: Session = Depends(get_db),
    verified: Optional[bool] = Query(default=None),
    resolved: Optional[bool] = Query(default=None),
    report_kind: Optional[str] = Query(default=None),
    report_subtype: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminObstacleReportResponse]:
    query = db.query(ObstacleReport)
    if verified is not None:
        query = query.filter(ObstacleReport.is_verified == verified)
    if resolved is not None:
        query = query.filter(ObstacleReport.is_resolved == resolved)
    if report_kind is not None:
        query = query.filter(ObstacleReport.report_kind == report_kind)
    if report_subtype is not None:
        query = query.filter(ObstacleReport.report_subtype == report_subtype)

    rows = (
        query.order_by(ObstacleReport.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    out: list[AdminObstacleReportResponse] = []
    for report in rows:
        verification_count = (
            db.query(ObstacleVerification)
            .filter(ObstacleVerification.obstacle_report_id == report.id)
            .count()
        )
        out.append(
            AdminObstacleReportResponse(
                id=report.id,
                latitude=report.latitude,
                longitude=report.longitude,
                obstacle_type=report.obstacle_type,
                report_kind=report.report_kind,
                report_subtype=report.report_subtype,
                subtype_source=report.subtype_source,
                description=report.description,
                severity=report.severity,
                is_temporary=report.is_temporary,
                is_verified=report.is_verified,
                is_resolved=report.is_resolved,
                image_url=report.image_url,
                created_at=report.created_at,
                reporter_id=report.reporter_id,
                verification_count=verification_count,
                verify_endpoint=f"/api/v1/obstacles/reports/{report.id}/verify",
                resolve_endpoint=f"/api/v1/obstacles/reports/{report.id}/resolve",
                unresolve_endpoint=f"/api/v1/obstacles/reports/{report.id}/unresolve",
                verify_request_body=ObstacleVerificationTemplate(),
                resolve_request_body=ObstacleResolveTemplate(),
                unresolve_request_body=ObstacleResolveTemplate(),
            )
        )
    return out


@router.post(
    "/obstacles/reports/{report_id}/image",
    response_model=ObstacleReportResponse,
    summary="Attach or replace report image evidence.",
)
async def upload_obstacle_report_image(
    report_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ObstacleReportResponse:
    report = db.query(ObstacleReport).filter(ObstacleReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Obstacle report not found")

    if file.content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"

    filename = f"report_{report_id}_{uuid4().hex}{ext}"
    dest = REPORT_UPLOAD_DIR / filename
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image file")
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")

    with open(dest, "wb") as f:
        f.write(content)

    # Keep URL simple so Swagger users can click it.
    report.image_url = f"/uploads/reports/{filename}"
    db.commit()
    db.refresh(report)
    return report


@router.post(
    "/obstacles/reports/{report_id}/verify",
    response_model=ObstacleReportResponse,
    summary="Submit a human verification for an obstacle report.",
    description=(
        "Records a verifier confirmation and may set is_verified when the verification "
        "count reaches OBSTACLE_VERIFICATION_THRESHOLD. Does not set is_resolved; use "
        "POST .../resolve or .../unresolve to change resolution."
    ),
)
def verify_obstacle_report(
    report_id: int,
    payload: ObstacleVerificationCreate,
    db: Session = Depends(get_db),
) -> ObstacleReportResponse:
    report = db.query(ObstacleReport).filter(ObstacleReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Obstacle report not found")

    # Verification must not change resolution; lock these before any commit (session
    # expiry / triggers / accidental dirty state should not flip is_resolved here).
    resolved_before = bool(report.is_resolved)
    resolved_at_before = report.resolved_at

    existing_verification = (
        db.query(ObstacleVerification)
        .filter(
            ObstacleVerification.obstacle_report_id == report.id,
            ObstacleVerification.verifier_id == payload.verifier_id,
        )
        .first()
    )
    if existing_verification is not None:
        raise HTTPException(
            status_code=409,
            detail="This verifier has already verified this obstacle report.",
        )

    # Record the verification event.
    verification = ObstacleVerification(
        obstacle_report_id=report.id,
        verifier_id=payload.verifier_id,
        notes=payload.notes,
    )
    db.add(verification)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This verifier has already verified this obstacle report.",
        ) from None

    # Compute how many independent confirmations exist and set `is_verified`.
    verification_count = (
        db.query(ObstacleVerification)
        .filter(ObstacleVerification.obstacle_report_id == report.id)
        .count()
    )

    report.is_verified = verification_count >= settings.OBSTACLE_VERIFICATION_THRESHOLD
    report.is_resolved = resolved_before
    report.resolved_at = resolved_at_before
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


@router.post(
    "/obstacles/reports/{report_id}/unresolve",
    response_model=ObstacleReportResponse,
    summary="Mark an obstacle report as unresolved/active again.",
)
def unresolve_obstacle_report(
    report_id: int,
    payload: ObstacleResolveCreate,
    db: Session = Depends(get_db),
) -> ObstacleReportResponse:
    # NOTE: this prototype unresolves without storing resolver_id audit trail.
    report = db.query(ObstacleReport).filter(ObstacleReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Obstacle report not found")

    report.is_resolved = False
    report.resolved_at = None
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
    if not settings.ML_ENABLED:
        await websocket.send_text(
            json.dumps({"error": "Realtime ML stream disabled (ML_ENABLED=false)"})
        )
        await websocket.close(code=1008)
        return

    from app.services.obstacle_classification import get_obstacle_classifier
    from app.services.verifier_classification import (
        get_obstruction_verifier,
        get_surface_problem_verifier,
    )

    classifier = get_obstacle_classifier()
    obstruction_verifier = get_obstruction_verifier()
    surface_problem_verifier = get_surface_problem_verifier()

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
            obstruction_raw = obstruction_verifier.predict_proba(image_bytes)
            surface_raw = surface_problem_verifier.predict_proba(image_bytes)

            obstacle_confidence = float(raw["confidence"])
            suggested_severity = max(1, min(5, int(round(obstacle_confidence * 5))))

            obstruction_yes_probability = float(obstruction_raw["yes_probability"])
            surface_problem_yes_probability = float(surface_raw["yes_probability"])
            obstruction_yes = obstruction_yes_probability >= 0.5
            surface_problem_yes = surface_problem_yes_probability >= 0.5

            # Choose what kind of report the client should create (single action).
            if obstruction_yes or surface_problem_yes:
                if obstruction_yes_probability >= surface_problem_yes_probability:
                    suggested_report_kind = "obstacle"
                    suggested_obstacle_type = raw["obstacle_type"]
                else:
                    suggested_report_kind = "surface_problem"
                    suggested_obstacle_type = ObstacleType.YES.value
            else:
                suggested_report_kind = "none"
                suggested_obstacle_type = None

            suggested_report_subtype = _suggest_report_subtype(
                suggested_report_kind=suggested_report_kind,
                obstacle_type=raw["obstacle_type"],
            )

            response: dict[str, object] = {
                "obstacle_type": raw["obstacle_type"],
                "confidence": obstacle_confidence,
                "probabilities": raw["probabilities"],
                "narrative_reasons": raw["narrative_reasons"],
                "checkpoint_loaded": raw["checkpoint_loaded"],
                "eligible_for_live_map": False,  # requires verification flow
                "suggested_severity": suggested_severity,
                "obstruction_yes_probability": obstruction_yes_probability,
                "obstruction_yes": obstruction_yes,
                "obstruction_verifier_checkpoint_loaded": obstruction_raw["checkpoint_loaded"],
                "surface_problem_yes_probability": surface_problem_yes_probability,
                "surface_problem_yes": surface_problem_yes,
                "surface_problem_verifier_checkpoint_loaded": surface_raw["checkpoint_loaded"],
                "suggested_report_kind": suggested_report_kind,
                "suggested_obstacle_type": suggested_obstacle_type,
                "suggested_report_subtype": suggested_report_subtype,
                "suggested_subtype_source": SubtypeSource.ML_SUGGESTED.value,
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
            }
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        return

