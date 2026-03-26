from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text

from app.config import settings
from app.database import get_db
from app.models.models import ObstacleReport
from app.schemas.schemas import HeatmapPoint, LGUHeatmapRequest, LGUReportResponse

router = APIRouter()


def _meters_to_latlon_steps(grid_meters: float, mean_lat: float) -> Tuple[float, float]:
    # Approximate conversions.
    lat_step_deg = grid_meters / 111_320.0
    lon_step_deg = grid_meters / (111_320.0 * max(0.2, math.cos(math.radians(mean_lat))))
    return lat_step_deg, lon_step_deg


@router.post(
    "/lgu/heatmap",
    response_model=LGUReportResponse,
    summary="Export a heatmap of inaccessibility for a bounding box.",
)
def export_lgu_heatmap(payload: LGUHeatmapRequest, db: Session = Depends(get_db)) -> LGUReportResponse:
    min_lat = payload.min_latitude
    min_lon = payload.min_longitude
    max_lat = payload.max_latitude
    max_lon = payload.max_longitude

    if min_lat > max_lat or min_lon > max_lon:
        # Basic sanity check; clients sometimes pass swapped bbox corners.
        min_lat, max_lat = min(max_lat, min_lat), max(max_lat, min_lat)
        min_lon, max_lon = min(max_lon, min_lon), max(max_lon, min_lon)

    mean_lat = (min_lat + max_lat) / 2.0
    lat_step, lon_step = _meters_to_latlon_steps(payload.grid_cell_size_meters, mean_lat)

    ttl_clause = or_(
        ObstacleReport.is_temporary == False,
        ObstacleReport.created_at
        >= func.now() - text(f"interval '{settings.TEMP_OBSTACLE_TTL_HOURS} hours'"),
    )

    bbox_filter = and_(
        ObstacleReport.latitude >= min_lat,
        ObstacleReport.latitude <= max_lat,
        ObstacleReport.longitude >= min_lon,
        ObstacleReport.longitude <= max_lon,
    )

    total_obstacles = db.query(ObstacleReport).filter(bbox_filter).count()

    unresolved_filter = and_(
        bbox_filter,
        ObstacleReport.is_resolved == False,
        ttl_clause,
    )

    unresolved_obstacles = db.query(ObstacleReport).filter(unresolved_filter).count()

    high_severity_count = (
        db.query(ObstacleReport)
        .filter(unresolved_filter, ObstacleReport.severity >= 4)
        .count()
    )

    heatmap_filter = unresolved_filter
    if payload.only_verified:
        heatmap_filter = and_(heatmap_filter, ObstacleReport.is_verified == True)

    obstacles = db.query(ObstacleReport).filter(heatmap_filter).all()

    # Bin into grid cells.
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
            subtype = (
                obs.report_subtype.value
                if getattr(obs, "report_subtype", None) is not None
                else "other"
            )
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

    # Stable ordering makes it easier to diff/test.
    heatmap_points.sort(key=lambda p: (p.latitude, p.longitude))

    return LGUReportResponse(
        report_date=datetime.utcnow(),
        total_obstacles=total_obstacles,
        unresolved_obstacles=unresolved_obstacles,
        high_severity_count=high_severity_count,
        heatmap_points=heatmap_points,
        csv_download_url=None,
    )

