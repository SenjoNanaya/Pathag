from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import ObstacleReport, ObstacleVerification
from app.schemas.schemas import (
    HeatmapPoint,
    LGUHeatmapRequest,
    LGUPlanningExportRequest,
    LGUReportResponse,
)

router = APIRouter()


def _meters_to_latlon_steps(grid_meters: float, mean_lat: float) -> Tuple[float, float]:
    lat_step_deg = grid_meters / 111_320.0
    lon_step_deg = grid_meters / (111_320.0 * max(0.2, math.cos(math.radians(mean_lat))))
    return lat_step_deg, lon_step_deg


def _normalize_bbox(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
) -> Tuple[float, float, float, float]:
    if min_lat > max_lat:
        min_lat, max_lat = max_lat, min_lat
    if min_lon > max_lon:
        min_lon, max_lon = max_lon, min_lon
    return min_lat, max_lat, min_lon, max_lon


def _ttl_clause():
    return or_(
        ObstacleReport.is_temporary == False,
        ObstacleReport.created_at
        >= func.now() - text(f"interval '{settings.TEMP_OBSTACLE_TTL_HOURS} hours'"),
    )


def _bbox_clause(min_lat: float, max_lat: float, min_lon: float, max_lon: float):
    return and_(
        ObstacleReport.latitude >= min_lat,
        ObstacleReport.latitude <= max_lat,
        ObstacleReport.longitude >= min_lon,
        ObstacleReport.longitude <= max_lon,
    )


def _workflow_status(obs: ObstacleReport) -> str:
    if obs.is_resolved:
        return "closed"
    if obs.is_verified:
        return "confirmed_open"
    return "reported_pending_review"


def _absolute_media_url(path: Optional[str]) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = (settings.PUBLIC_API_BASE_URL or "").rstrip("/")
    if not base:
        return path
    p = path if path.startswith("/") else f"/{path}"
    return f"{base}{p}"


def _verification_counts(db: Session, report_ids: List[int]) -> Dict[int, int]:
    if not report_ids:
        return {}
    try:
        rows = (
            db.query(
                ObstacleVerification.obstacle_report_id,
                func.count(ObstacleVerification.id),
            )
            .filter(ObstacleVerification.obstacle_report_id.in_(report_ids))
            .group_by(ObstacleVerification.obstacle_report_id)
            .all()
        )
    except ProgrammingError as exc:
        # Backward compatibility for partially migrated DBs where the
        # obstacle_verifications table does not exist yet.
        db.rollback()
        err = str(getattr(exc, "orig", exc)).lower()
        if "obstacle_verifications" not in err:
            raise
        return {}
    return {int(rid): int(c) for rid, c in rows}


def _planning_reports_query(db: Session, req: LGUPlanningExportRequest):
    min_lat, max_lat, min_lon, max_lon = _normalize_bbox(
        req.min_latitude,
        req.max_latitude,
        req.min_longitude,
        req.max_longitude,
    )
    q = db.query(ObstacleReport).filter(_bbox_clause(min_lat, max_lat, min_lon, max_lon))
    if not req.include_resolved:
        q = q.filter(ObstacleReport.is_resolved == False)
    if req.only_verified:
        q = q.filter(ObstacleReport.is_verified == True)
    if req.min_severity is not None:
        q = q.filter(ObstacleReport.severity >= req.min_severity)
    if req.respect_temporary_ttl:
        q = q.filter(_ttl_clause())
    return q.order_by(ObstacleReport.created_at.desc())


def _enum_str(val) -> str:
    if val is None:
        return ""
    return val.value if hasattr(val, "value") else str(val)


def _dt_iso(dt) -> str:
    if dt is None:
        return ""
    if getattr(dt, "tzinfo", None) is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(sep=" ", timespec="seconds")


@router.post(
    "/lgu/heatmap",
    response_model=LGUReportResponse,
    summary="Export a heatmap of inaccessibility for a bounding box.",
    description=(
        "Aggregates unresolved reports into a grid for dashboards. "
        "Includes subtype/kind breakdowns for planning prioritization (see also "
        "POST /lgu/planning/reports.csv and /lgu/planning/reports.geojson for GIS)."
    ),
)
def export_lgu_heatmap(payload: LGUHeatmapRequest, db: Session = Depends(get_db)) -> LGUReportResponse:
    min_lat, max_lat, min_lon, max_lon = _normalize_bbox(
        payload.min_latitude,
        payload.max_latitude,
        payload.min_longitude,
        payload.max_longitude,
    )

    mean_lat = (min_lat + max_lat) / 2.0
    lat_step, lon_step = _meters_to_latlon_steps(payload.grid_cell_size_meters, mean_lat)

    bbox_filter = _bbox_clause(min_lat, max_lat, min_lon, max_lon)

    total_obstacles = db.query(ObstacleReport).filter(bbox_filter).count()

    unresolved_filter = and_(
        bbox_filter,
        ObstacleReport.is_resolved == False,
        _ttl_clause(),
    )

    unresolved_obstacles = db.query(ObstacleReport).filter(unresolved_filter).count()

    high_severity_count = (
        db.query(ObstacleReport)
        .filter(unresolved_filter, ObstacleReport.severity >= 4)
        .count()
    )

    # Rollups for planners: all unresolved in bbox (not restricted to only_verified).
    planning_rows = db.query(ObstacleReport).filter(unresolved_filter).all()
    subtype_breakdown = Counter()
    report_kind_breakdown = Counter()
    for obs in planning_rows:
        subtype_breakdown[_enum_str(obs.report_subtype) or "other"] += 1
        report_kind_breakdown[_enum_str(obs.report_kind) or "unknown"] += 1

    heatmap_filter = unresolved_filter
    if payload.only_verified:
        heatmap_filter = and_(heatmap_filter, ObstacleReport.is_verified == True)

    obstacles = db.query(ObstacleReport).filter(heatmap_filter).all()

    bins: Dict[Tuple[int, int], Dict[str, object]] = {}
    for obs in obstacles:
        i = int((obs.latitude - min_lat) / lat_step) if lat_step > 0 else 0
        j = int((obs.longitude - min_lon) / lon_step) if lon_step > 0 else 0
        key = (i, j)
        if key not in bins:
            bins[key] = {"severity_sum": 0.0, "count": 0, "subtype_counts": {}}
        bins[key]["severity_sum"] = float(bins[key]["severity_sum"]) + float(obs.severity)
        bins[key]["count"] = int(bins[key]["count"]) + 1
        subtype_counts = bins[key]["subtype_counts"]
        if isinstance(subtype_counts, dict):
            subtype = _enum_str(obs.report_subtype) or "other"
            subtype_counts[subtype] = int(subtype_counts.get(subtype, 0)) + 1

    heatmap_points: List[HeatmapPoint] = []
    for (i, j), agg in bins.items():
        count = int(agg["count"])
        if count <= 0:
            continue
        cell_center_lat = min_lat + (i + 0.5) * lat_step
        cell_center_lon = min_lon + (j + 0.5) * lon_step
        subtype_counts = agg.get("subtype_counts", {})
        heatmap_points.append(
            HeatmapPoint(
                latitude=cell_center_lat,
                longitude=cell_center_lon,
                severity=round(float(agg["severity_sum"]) / count, 2),
                obstacle_count=count,
                subtype_counts=subtype_counts if isinstance(subtype_counts, dict) else {},
            )
        )

    heatmap_points.sort(key=lambda p: (p.latitude, p.longitude))

    return LGUReportResponse(
        report_date=datetime.utcnow(),
        total_obstacles=total_obstacles,
        unresolved_obstacles=unresolved_obstacles,
        high_severity_count=high_severity_count,
        heatmap_points=heatmap_points,
        csv_download_url=None,
        subtype_breakdown=dict(sorted(subtype_breakdown.items())),
        report_kind_breakdown=dict(sorted(report_kind_breakdown.items())),
    )


def _csv_row_for_report(
    obs: ObstacleReport,
    verification_count: int,
) -> List[object]:
    desc = obs.description or ""
    desc_clean = desc.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    lon, lat = obs.longitude, obs.latitude
    wkt = f"POINT ({lon} {lat})"
    return [
        obs.id,
        lat,
        lon,
        wkt,
        _enum_str(obs.report_kind),
        _enum_str(obs.report_subtype),
        _enum_str(obs.obstacle_type),
        _enum_str(obs.subtype_source),
        obs.severity,
        bool(obs.is_verified),
        verification_count,
        bool(obs.is_resolved),
        bool(obs.is_temporary),
        _workflow_status(obs),
        _dt_iso(obs.created_at),
        _dt_iso(obs.resolved_at),
        obs.reporter_id if obs.reporter_id is not None else "",
        desc_clean,
        obs.image_url or "",
        _absolute_media_url(obs.image_url),
    ]


CSV_HEADER = [
    "id",
    "latitude_wgs84",
    "longitude_wgs84",
    "wkt_point_epsg4326",
    "report_kind",
    "report_subtype",
    "obstacle_type",
    "subtype_source",
    "severity_1_to_5",
    "is_verified",
    "verification_count",
    "is_resolved",
    "is_temporary",
    "workflow_status",
    "created_at_utc",
    "resolved_at_utc",
    "reporter_id",
    "description",
    "image_url_path",
    "image_url_absolute",
]


@router.post(
    "/lgu/planning/reports.csv",
    summary="Download obstacle reports as CSV (Excel, maintenance systems).",
    description=(
        "Columns are chosen for urban mobility / public works workflows: WKT for GIS import, "
        "workflow_status for triage (confirmed_open vs reported_pending_review), "
        "verification_count for QA. Set PUBLIC_API_BASE_URL in the API environment for "
        "clickable photo evidence links."
    ),
    response_class=StreamingResponse,
)
def export_planning_reports_csv(
    payload: LGUPlanningExportRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    reports: List[ObstacleReport] = _planning_reports_query(db, payload).all()
    ids = [r.id for r in reports]
    vmap = _verification_counts(db, ids)

    def rows() -> Iterator[str]:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(CSV_HEADER)
        yield "\ufeff" + buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for obs in reports:
            w.writerow(_csv_row_for_report(obs, vmap.get(obs.id, 0)))
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"pathag_accessibility_reports_{stamp}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(rows(), media_type="text/csv", headers=headers)


@router.post(
    "/lgu/planning/reports.geojson",
    summary="Download obstacle reports as GeoJSON (QGIS, ArcGIS Online).",
    description=(
        "RFC 7946 FeatureCollection of points in EPSG:4326. Import as a vector layer and "
        "spatially join to footways / roads from OpenStreetMap for capital planning."
    ),
)
def export_planning_reports_geojson(
    payload: LGUPlanningExportRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    reports: List[ObstacleReport] = _planning_reports_query(db, payload).all()
    ids = [r.id for r in reports]
    vmap = _verification_counts(db, ids)

    features: List[dict] = []
    for obs in reports:
        vc = vmap.get(obs.id, 0)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(obs.longitude), float(obs.latitude)],
                },
                "properties": {
                    "id": obs.id,
                    "report_kind": _enum_str(obs.report_kind),
                    "report_subtype": _enum_str(obs.report_subtype),
                    "obstacle_type": _enum_str(obs.obstacle_type),
                    "subtype_source": _enum_str(obs.subtype_source),
                    "severity": obs.severity,
                    "is_verified": obs.is_verified,
                    "verification_count": vc,
                    "is_resolved": obs.is_resolved,
                    "is_temporary": obs.is_temporary,
                    "workflow_status": _workflow_status(obs),
                    "created_at_utc": _dt_iso(obs.created_at),
                    "resolved_at_utc": _dt_iso(obs.resolved_at),
                    "reporter_id": obs.reporter_id,
                    "description": (obs.description or "").replace("\n", " "),
                    "image_url_path": obs.image_url or "",
                    "image_url_absolute": _absolute_media_url(obs.image_url),
                },
            }
        )

    body = {
        "type": "FeatureCollection",
        "name": "pathag_accessibility_reports",
        "generated_at_utc": datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
        "crs_hint": "EPSG:4326 (GeoJSON RFC 7946)",
        "features": features,
    }
    return JSONResponse(content=body, media_type="application/geo+json")


@router.post(
    "/lgu/planning/heatmap_cells.csv",
    summary="Download heatmap grid cells as CSV (same logic as /lgu/heatmap).",
    description=(
        "One row per non-empty grid cell: center coordinates, report count, mean severity, "
        "and subtype counts as JSON for pivot tables."
    ),
    response_class=StreamingResponse,
)
def export_planning_heatmap_csv(
    payload: LGUHeatmapRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    summary = export_lgu_heatmap(payload, db)

    def rows() -> Iterator[str]:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "cell_center_latitude",
                "cell_center_longitude",
                "grid_cell_size_meters",
                "obstacle_count",
                "mean_severity",
                "subtype_counts_json",
            ]
        )
        yield "\ufeff" + buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for p in summary.heatmap_points:
            w.writerow(
                [
                    p.latitude,
                    p.longitude,
                    payload.grid_cell_size_meters,
                    p.obstacle_count,
                    p.severity,
                    json.dumps(p.subtype_counts, sort_keys=True),
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"pathag_heatmap_cells_{stamp}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(rows(), media_type="text/csv", headers=headers)
