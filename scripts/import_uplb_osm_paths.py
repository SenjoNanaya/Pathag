"""
Import walkable OSM ways around UPLB into `path_segments`.

Usage:
  python scripts/import_uplb_osm_paths.py
  python scripts/import_uplb_osm_paths.py --replace-osm
  python scripts/import_uplb_osm_paths.py --bbox "14.1540,121.2300,14.1825,121.2555"
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

# Ensure `app` package is importable when running as a script.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models.models import PathCondition, PathSegment


DEFAULT_BBOX = "14.1540,121.2300,14.1825,121.2555"  # south,west,north,east
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@dataclass
class ImportStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def _build_overpass_query(bbox: str) -> str:
    # Prefer pedestrian-first ways and exclude access-restricted links.
    return f"""
[out:json][timeout:120];
(
  way["highway"~"footway|path|pedestrian|steps"]["access"!~"private|no"]["foot"!~"no"]({bbox});
  way["footway"="sidewalk"]["access"!~"private|no"]["foot"!~"no"]({bbox});
);
out geom;
""".strip()


def _line_wkt_from_geometry(geometry: List[Dict[str, float]]) -> Optional[str]:
    if len(geometry) < 2:
        return None
    parts = [f"{pt['lon']} {pt['lat']}" for pt in geometry]
    return f"LINESTRING({', '.join(parts)})"


def _path_condition_and_score(tags: Dict[str, str]) -> Tuple[PathCondition, float]:
    highway = tags.get("highway", "")
    surface = tags.get("surface", "")
    smoothness = tags.get("smoothness", "")
    footway = tags.get("footway", "")

    if highway == "steps":
        return PathCondition.OBSTRUCTED, 0.2

    if surface in {"unpaved", "dirt", "ground", "gravel", "sand", "grass"}:
        return PathCondition.UNEVEN, 0.55

    if smoothness in {"bad", "very_bad", "horrible", "very_horrible", "impassable"}:
        return PathCondition.CRACKED, 0.5

    if footway == "sidewalk" or highway in {"footway", "pedestrian"}:
        return PathCondition.SMOOTH, 0.95

    if highway == "path":
        # Generic paths are still walkable but less preferred than sidewalks.
        return PathCondition.CRACKED, 0.72

    return PathCondition.SMOOTH, 0.9


def _iter_way_elements(payload: Dict[str, object]) -> Iterable[Dict[str, object]]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        return []
    for element in elements:
        if isinstance(element, dict) and element.get("type") == "way":
            yield element


def _upsert_way(db: Session, way: Dict[str, object], existing_by_source: Dict[str, PathSegment]) -> str:
    way_id = way.get("id")
    geom = way.get("geometry")
    tags = way.get("tags") or {}
    if not isinstance(way_id, int) or not isinstance(geom, list) or not isinstance(tags, dict):
        return "skipped"

    geometry = [pt for pt in geom if isinstance(pt, dict) and "lat" in pt and "lon" in pt]
    if len(geometry) < 2:
        return "skipped"

    line_wkt = _line_wkt_from_geometry(geometry)
    if line_wkt is None:
        return "skipped"

    source = f"osm:{way_id}"
    condition, accessibility_score = _path_condition_and_score(tags)
    width_meters = None
    width_raw = tags.get("width")
    if isinstance(width_raw, str):
        try:
            width_meters = float(width_raw.replace("m", "").strip())
        except ValueError:
            width_meters = None

    start = geometry[0]
    end = geometry[-1]

    segment = existing_by_source.get(source)
    if segment is None:
        segment = PathSegment(
            geometry=WKTElement(line_wkt, srid=4326),
            start_lat=float(start["lat"]),
            start_lon=float(start["lon"]),
            end_lat=float(end["lat"]),
            end_lon=float(end["lon"]),
            condition=condition,
            accessibility_score=accessibility_score,
            width_meters=width_meters,
            source=source,
            confidence_score=0.85,
        )
        db.add(segment)
        existing_by_source[source] = segment
        return "inserted"

    segment.geometry = WKTElement(line_wkt, srid=4326)
    segment.start_lat = float(start["lat"])
    segment.start_lon = float(start["lon"])
    segment.end_lat = float(end["lat"])
    segment.end_lon = float(end["lon"])
    segment.condition = condition
    segment.accessibility_score = accessibility_score
    segment.width_meters = width_meters
    segment.confidence_score = 0.85
    return "updated"


def run_import(
    *,
    bbox: str,
    overpass_url: str,
    replace_osm: bool,
) -> ImportStats:
    query = _build_overpass_query(bbox)

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(overpass_url, data={"data": query})
        resp.raise_for_status()
        payload = resp.json()

    db = SessionLocal()
    try:
        if replace_osm:
            db.query(PathSegment).filter(PathSegment.source.like("osm:%")).delete(
                synchronize_session=False
            )
            db.commit()

        existing_segments = (
            db.query(PathSegment)
            .filter(PathSegment.source.like("osm:%"))
            .all()
        )
        existing_by_source = {seg.source: seg for seg in existing_segments if seg.source}

        stats = ImportStats()
        for way in _iter_way_elements(payload):
            outcome = _upsert_way(db, way, existing_by_source)
            if outcome == "inserted":
                stats.inserted += 1
            elif outcome == "updated":
                stats.updated += 1
            else:
                stats.skipped += 1

        db.commit()
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import OSM walkable paths into path_segments for local routing."
    )
    parser.add_argument(
        "--bbox",
        default=DEFAULT_BBOX,
        help="Bounding box as south,west,north,east",
    )
    parser.add_argument(
        "--overpass-url",
        default=DEFAULT_OVERPASS_URL,
        help="Overpass API interpreter endpoint",
    )
    parser.add_argument(
        "--replace-osm",
        action="store_true",
        help="Delete existing osm:* path_segments before import",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = run_import(
        bbox=args.bbox,
        overpass_url=args.overpass_url,
        replace_osm=args.replace_osm,
    )
    print(
        "OSM import complete: "
        f"{stats.inserted} inserted, "
        f"{stats.updated} updated, "
        f"{stats.skipped} skipped."
    )


if __name__ == "__main__":
    main()
