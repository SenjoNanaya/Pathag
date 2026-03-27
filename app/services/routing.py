"""
Routing Service - Accessibility-Aware Pathfinding
Calculates routes with accessibility scoring and user preference application
"""
import logging
import math
import heapq
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text, cast
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Point
from geoalchemy2.elements import WKTElement
from geoalchemy2 import Geography

import httpx

from app.models.models import (
    ObstacleReport,
    ObstacleSubtype,
    ObstacleType,
    PathCondition,
    PathSegment,
    User,
)
from app.config import settings
from app.schemas.schemas import (
    Coordinate,
    RouteAlternativeResponse,
    RouteObstacleDiagnostics,
    RouteRequest,
    RouteResponse,
    RouteStep,
)

logger = logging.getLogger(__name__)


class RoutingService:    
    def __init__(self, db: Session):
        self.db = db
    
    async def calculate_route(
        self, 
        request: RouteRequest,
        user: Optional[User] = None
    ) -> RouteResponse:
        # 1) Get candidate routes (ORS alternatives if configured; otherwise fallback).
        route_candidates = await self._generate_route_candidates(request.origin, request.destination)

        best = None
        best_idx: Optional[int] = None
        best_score = -1.0
        min_distance: Optional[float] = None
        candidate_evals: List[Dict[str, object]] = []

        # 2) Score each candidate by accessibility and select the best.
        for idx, coordinates in enumerate(route_candidates):
            obstacles = self._get_obstacles_along_route(coordinates, buffer_meters=settings.OBSTACLE_ROUTE_BUFFER_METERS)
            distance = self._calculate_route_distance(coordinates)
            accessibility_score = self._calculate_accessibility_score(
                coordinates=coordinates,
                obstacles=obstacles,
                request=request,
                user=user,
            )
            candidate_evals.append(
                {
                    "idx": idx,
                    "coordinates": coordinates,
                    "obstacles": obstacles,
                    "distance": distance,
                    "accessibility": accessibility_score,
                }
            )
            if min_distance is None or distance < min_distance:
                min_distance = distance

        if min_distance is None:
            min_distance = 1.0

        # Prefer accessibility, but penalize extreme detours.
        for candidate in candidate_evals:
            distance = float(candidate["distance"])
            accessibility_score = float(candidate["accessibility"])
            detour_ratio = max(0.0, (distance - min_distance) / max(min_distance, 1.0))
            detour_penalty = min(0.40, detour_ratio * 0.20)
            blended_score = accessibility_score - detour_penalty
            candidate["blended"] = blended_score
            if blended_score > best_score:
                best_score = blended_score
                best_idx = int(candidate["idx"])
                best = {
                    "idx": int(candidate["idx"]),
                    "coordinates": candidate["coordinates"],
                    "obstacles": candidate["obstacles"],
                    "distance": distance,
                    "accessibility_score": accessibility_score,
                }

        assert best is not None  # for type-checkers; route_candidates always has >= 1
        coordinates = best["coordinates"]
        obstacles = best["obstacles"]

        # 3) Final metrics for the selected route.
        distance = float(best.get("distance", self._calculate_route_distance(coordinates)))
        duration = self._estimate_duration(distance)
        steps = self._generate_route_steps(coordinates, obstacles)
        warnings = self._generate_warnings(request, obstacles, user)
        obstacle_diagnostics = self._build_obstacle_diagnostics(
            coordinates=coordinates,
            buffer_meters=settings.OBSTACLE_ROUTE_BUFFER_METERS,
            eligible_obstacles=obstacles,
        )

        alternatives: List[RouteAlternativeResponse] = []
        sorted_candidates = sorted(
            candidate_evals,
            key=lambda c: float(c.get("blended", -999.0)),
            reverse=True,
        )
        for candidate in sorted_candidates:
            if best_idx is not None and int(candidate["idx"]) == best_idx:
                continue
            alt_coordinates = candidate["coordinates"]
            alt_obstacles = candidate["obstacles"]
            alt_distance = float(candidate["distance"])
            alt_steps = self._generate_route_steps(alt_coordinates, alt_obstacles)
            alt_warnings = self._generate_warnings(request, alt_obstacles, user)
            alternatives.append(
                RouteAlternativeResponse(
                    distance_meters=alt_distance,
                    estimated_duration_seconds=self._estimate_duration(alt_distance),
                    accessibility_score=float(candidate["accessibility"]),
                    coordinates=alt_coordinates,
                    steps=alt_steps,
                    warnings=alt_warnings,
                )
            )
            # Keep payload compact for mobile while still exposing choices.
            if len(alternatives) >= 2:
                break

        return RouteResponse(
            distance_meters=distance,
            estimated_duration_seconds=duration,
            accessibility_score=float(best.get("accessibility_score", best_score)),
            coordinates=coordinates,
            steps=steps,
            warnings=warnings,
            obstacle_diagnostics=obstacle_diagnostics,
            alternative_routes=alternatives,
        )
    
    async def _generate_route_candidates(
        self,
        origin: Coordinate,
        destination: Coordinate,
        num_candidates_fallback: int = 1,
    ) -> List[List[List[float]]]:
        """
        Returns a list of alternative routes.

        Each route is encoded as `[[lon, lat], ...]`.
        """

        if settings.ORS_API_KEY:
            try:
                coords_list = await self._fetch_ors_route_alternatives(origin, destination)
                # ORS does not see our path_segment conditions; add avoid_polygons from
                # verified reports and from locally mapped poor segments (e.g. uneven park paths).
                avoid_obstacles = self._get_critical_avoid_obstacles()
                avoid_variant = await self._fetch_ors_route_avoiding_obstacles(
                    origin=origin,
                    destination=destination,
                    obstacles=avoid_obstacles,
                )
                if avoid_variant:
                    coords_list.append(avoid_variant)
                if coords_list:
                    return coords_list
            except Exception:
                # ORS issues should not take down the entire routing service.
                pass

        # Fallback #1: use known path-segment network from PostGIS if available.
        network_route = self._generate_path_network_route(origin, destination)
        if network_route:
            return [network_route]

        # Fallback: simplified demo routing (single candidate).
        return [self._generate_route_coordinates(origin, destination)]

    def _generate_path_network_route(
        self,
        origin: Coordinate,
        destination: Coordinate,
    ) -> Optional[List[List[float]]]:
        rows = (
            self.db.query(
                PathSegment.id,
                PathSegment.start_lat,
                PathSegment.start_lon,
                PathSegment.end_lat,
                PathSegment.end_lon,
                PathSegment.condition,
                PathSegment.slope_percentage,
                PathSegment.accessibility_score,
                func.ST_AsGeoJSON(PathSegment.geometry).label("geometry_json"),
            )
            .all()
        )
        if not rows:
            return None

        node_index_by_key: Dict[Tuple[float, float], int] = {}
        node_coords: List[Tuple[float, float]] = []  # (lat, lon)
        adjacency: Dict[int, List[Dict[str, Any]]] = {}

        def get_node_id(lat: float, lon: float) -> int:
            key = (round(float(lat), 6), round(float(lon), 6))
            existing = node_index_by_key.get(key)
            if existing is not None:
                return existing
            idx = len(node_coords)
            node_index_by_key[key] = idx
            node_coords.append((float(lat), float(lon)))
            adjacency[idx] = []
            return idx

        for row in rows:
            u = get_node_id(row.start_lat, row.start_lon)
            v = get_node_id(row.end_lat, row.end_lon)

            segment_coords: List[List[float]] = [
                [float(row.start_lon), float(row.start_lat)],
                [float(row.end_lon), float(row.end_lat)],
            ]
            geom = getattr(row, "geometry_json", None)
            if geom:
                try:
                    geojson = json.loads(geom)
                    raw_coords = geojson.get("coordinates")
                    if isinstance(raw_coords, list) and len(raw_coords) >= 2:
                        segment_coords = [
                            [float(lon), float(lat)] for lon, lat in raw_coords
                        ]
                except (ValueError, TypeError):
                    pass

            segment_length = self._calculate_route_distance(segment_coords)
            segment_cost = segment_length * self._segment_penalty_multiplier(
                condition=row.condition,
                slope_percentage=row.slope_percentage,
                accessibility_score=row.accessibility_score,
            )

            adjacency[u].append(
                {
                    "to": v,
                    "cost": segment_cost,
                    "coords": segment_coords,
                }
            )
            adjacency[v].append(
                {
                    "to": u,
                    "cost": segment_cost,
                    "coords": list(reversed(segment_coords)),
                }
            )

        start_node, start_distance = self._nearest_node_for_coordinate(
            origin.latitude,
            origin.longitude,
            node_coords,
        )
        end_node, end_distance = self._nearest_node_for_coordinate(
            destination.latitude,
            destination.longitude,
            node_coords,
        )
        if start_node is None or end_node is None:
            return None

        # If origin/destination are too far from mapped sidewalk/path nodes,
        # avoid pretending we have a reliable sidewalk route.
        if start_distance > 45 or end_distance > 45:
            return None

        node_path_coords = self._dijkstra_path_coordinates(
            start_node=start_node,
            end_node=end_node,
            adjacency=adjacency,
        )
        if not node_path_coords:
            return None

        full_route: List[List[float]] = []
        if node_path_coords:
            # Avoid drawing unrealistic connectors from building centroid points.
            # If landmark is not very close to the graph, start/end at snapped node.
            if start_distance <= 10:
                full_route.append([origin.longitude, origin.latitude])

            for coord in node_path_coords:
                if not full_route or coord != full_route[-1]:
                    full_route.append(coord)

            if end_distance <= 10:
                dest_coord = [destination.longitude, destination.latitude]
                if dest_coord != full_route[-1]:
                    full_route.append(dest_coord)

        return full_route if len(full_route) >= 2 else None

    def _dijkstra_path_coordinates(
        self,
        *,
        start_node: int,
        end_node: int,
        adjacency: Dict[int, List[Dict[str, Any]]],
    ) -> Optional[List[List[float]]]:
        if start_node == end_node:
            return []

        distances: Dict[int, float] = {start_node: 0.0}
        previous: Dict[int, Tuple[int, List[List[float]]]] = {}
        heap: List[Tuple[float, int]] = [(0.0, start_node)]

        while heap:
            dist, node = heapq.heappop(heap)
            if dist > distances.get(node, float("inf")):
                continue
            if node == end_node:
                break

            for edge in adjacency.get(node, []):
                nxt = int(edge["to"])
                next_dist = dist + float(edge["cost"])
                if next_dist < distances.get(nxt, float("inf")):
                    distances[nxt] = next_dist
                    previous[nxt] = (node, edge["coords"])
                    heapq.heappush(heap, (next_dist, nxt))

        if end_node not in previous:
            return None

        path_segments: List[List[List[float]]] = []
        cur = end_node
        while cur != start_node:
            prev_node, seg_coords = previous[cur]
            path_segments.append(seg_coords)
            cur = prev_node
        path_segments.reverse()

        flattened: List[List[float]] = []
        for segment in path_segments:
            for coord in segment:
                if not flattened or coord != flattened[-1]:
                    flattened.append(coord)
        return flattened

    def _nearest_node_for_coordinate(
        self,
        latitude: float,
        longitude: float,
        node_coords: List[Tuple[float, float]],
    ) -> Tuple[Optional[int], float]:
        if not node_coords:
            return None, float("inf")

        best_idx: Optional[int] = None
        best_dist = float("inf")
        for idx, (lat, lon) in enumerate(node_coords):
            dist = self._calculate_segment_distance(latitude, longitude, lat, lon)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx, best_dist

    def _segment_penalty_multiplier(
        self,
        *,
        condition: Optional[PathCondition],
        slope_percentage: Optional[float],
        accessibility_score: Optional[float],
    ) -> float:
        multiplier = 1.0

        if condition in (PathCondition.OBSTRUCTED, PathCondition.UNDER_CONSTRUCTION):
            multiplier *= 3.0
        elif condition in (PathCondition.UNEVEN, PathCondition.CRACKED):
            multiplier *= 1.5

        slope = float(slope_percentage) if slope_percentage is not None else 0.0
        if slope >= 12:
            multiplier *= 2.5
        elif slope >= 8:
            multiplier *= 1.7
        elif slope >= 5:
            multiplier *= 1.3

        if accessibility_score is not None:
            score = max(0.0, min(1.0, float(accessibility_score)))
            multiplier *= 1.0 + ((1.0 - score) * 3.0)

        return multiplier

    async def _fetch_ors_route_alternatives(
        self,
        origin: Coordinate,
        destination: Coordinate,
    ) -> List[List[List[float]]]:
        """
        Calls OpenRouteService directions endpoint and returns alternative geometries.

        The response structure can vary by ORS version/settings; parsing is defensive.
        """

        # ORS geojson endpoint returns raw coordinate arrays (no polyline decode needed).
        url = f"{settings.ORS_BASE_URL}/directions/{settings.ORS_PROFILE}/geojson"
        headers = {"Authorization": settings.ORS_API_KEY}
        payload = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "instructions": False,
        }
        if settings.ORS_ALTERNATIVES and settings.ORS_ALTERNATIVES > 1:
            payload["alternative_routes"] = {
                "target_count": settings.ORS_ALTERNATIVES,
            }

        async with httpx.AsyncClient(timeout=settings.ORS_REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        coords_list: List[List[List[float]]] = []
        features = data.get("features") or []
        if isinstance(features, list):
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                geometry = feature.get("geometry")
                if not isinstance(geometry, dict):
                    continue
                coords = geometry.get("coordinates")
                if not isinstance(coords, list) or not coords:
                    continue
                coords_list.append([[float(lon), float(lat)] for lon, lat in coords])

        # Backward-compatible parser for non-geojson response formats.
        if not coords_list:
            routes = data.get("routes") or []
            for route in routes:
                geom = route.get("geometry")
                if not geom:
                    continue
                if isinstance(geom, dict) and "coordinates" in geom:
                    coords = geom["coordinates"]
                elif isinstance(geom, list):
                    coords = geom
                else:
                    continue
                if coords:
                    coords_list.append([[float(lon), float(lat)] for lon, lat in coords])

        return coords_list

    async def _fetch_ors_route_avoiding_obstacles(
        self,
        *,
        origin: Coordinate,
        destination: Coordinate,
        obstacles: List[ObstacleReport],
    ) -> Optional[List[List[float]]]:
        avoid_polygons = self._build_ors_combined_avoid_multipolygon(
            origin=origin,
            destination=destination,
            obstacles=obstacles,
        )
        if avoid_polygons is None:
            return None

        url = f"{settings.ORS_BASE_URL}/directions/{settings.ORS_PROFILE}/geojson"
        headers = {"Authorization": settings.ORS_API_KEY}
        payload = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "instructions": False,
            "options": {
                "avoid_polygons": avoid_polygons,
            },
        }

        async with httpx.AsyncClient(timeout=settings.ORS_REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "ORS avoid_polygons rejected or failed: status=%s body=%s",
                    resp.status_code,
                    (resp.text or "")[:800],
                )
                return None
            data = resp.json()

        features = data.get("features") or []
        if not isinstance(features, list) or not features:
            return None
        feature = features[0]
        if not isinstance(feature, dict):
            return None
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            return None
        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or not coords:
            return None
        return [[float(lon), float(lat)] for lon, lat in coords]

    def _get_critical_avoid_obstacles(self) -> List[ObstacleReport]:
        ttl_clause = or_(
            ObstacleReport.is_temporary == False,
            ObstacleReport.created_at
            >= func.now() - text(f"interval '{settings.TEMP_OBSTACLE_TTL_HOURS} hours'"),
        )
        return (
            self.db.query(ObstacleReport)
            .filter(
                and_(
                    ObstacleReport.is_resolved == False,
                    ObstacleReport.is_verified == True,
                    ObstacleReport.obstacle_type == ObstacleType.YES,
                    ttl_clause,
                )
            )
            .all()
        )

    def _build_ors_combined_avoid_multipolygon(
        self,
        *,
        origin: Coordinate,
        destination: Coordinate,
        obstacles: List[ObstacleReport],
    ) -> Optional[Dict[str, object]]:
        """
        Build ORS avoid_polygons from verified obstacle points plus local path_segments
        tagged with poor surface/access (ORS never sees those edge weights otherwise).
        """
        polygons: List[List[List[List[float]]]] = []
        max_total = max(1, int(settings.ORS_AVOID_MAX_TOTAL_POLYGONS))

        for obs in obstacles:
            ring = self._circle_ring_lonlat(
                lat=obs.latitude,
                lon=obs.longitude,
                radius_meters=float(settings.ORS_AVOID_REPORT_RADIUS_M),
                points=18,
            )
            if len(ring) >= 4:
                polygons.append([ring])

        reserved = len(polygons)
        segment_budget = max(0, max_total - reserved)
        segment_budget = min(segment_budget, max(0, int(settings.ORS_SEGMENT_AVOID_MAX_RINGS)))
        if settings.ORS_SEGMENT_AVOID_ENABLED and segment_budget > 0:
            seg_rings = self._build_path_segment_avoid_rings(
                origin=origin,
                destination=destination,
                max_rings=segment_budget,
            )
            for ring in seg_rings:
                polygons.append([ring])

        if not polygons:
            return None
        return {
            "type": "MultiPolygon",
            "coordinates": polygons[:max_total],
        }

    def _ors_avoid_radius_for_path_condition(self, condition: PathCondition) -> float:
        if condition in (
            PathCondition.OBSTRUCTED,
            PathCondition.UNDER_CONSTRUCTION,
            PathCondition.NO_SIDEWALK,
        ):
            return float(settings.ORS_SEGMENT_AVOID_RADIUS_BAD_M)
        return float(settings.ORS_SEGMENT_AVOID_RADIUS_UNEVEN_M)

    def _coords_touch_route_bbox(
        self,
        coords: List[List[float]],
        *,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
    ) -> bool:
        for lon, lat in coords:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                return True
        return False

    def _distance_point_to_od_segment_m(
        self,
        plat: float,
        plon: float,
        olat: float,
        olon: float,
        dlat: float,
        dlon: float,
    ) -> float:
        ref_lat = (olat + dlat + plat) / 3.0
        px, py = self._latlon_to_local_xy(plat, plon, ref_lat)
        x1, y1 = self._latlon_to_local_xy(olat, olon, ref_lat)
        x2, y2 = self._latlon_to_local_xy(dlat, dlon, ref_lat)
        dx = x2 - x1
        dy = y2 - y1
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq <= 1e-6:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        qx = x1 + t * dx
        qy = y1 + t * dy
        return math.hypot(px - qx, py - qy)

    def _sample_points_along_linestring(
        self,
        coords: List[List[float]],
        step_meters: float,
    ) -> List[Tuple[float, float]]:
        """LineString [[lon, lat], ...] -> (lat, lon) samples including endpoints."""
        if not coords:
            return []
        step_meters = max(4.0, float(step_meters))
        out: List[Tuple[float, float]] = []
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]
            seg_len = self._calculate_segment_distance(lat1, lon1, lat2, lon2)
            if seg_len < 0.5:
                out.append((lat1, lon1))
                continue
            steps = max(1, int(math.ceil(seg_len / step_meters)))
            for s in range(steps + 1):
                t = min(1.0, s / steps) if steps else 0.0
                lat = lat1 + t * (lat2 - lat1)
                lon = lon1 + t * (lon2 - lon1)
                out.append((lat, lon))
        lon_e, lat_e = coords[-1][0], coords[-1][1]
        if not out or abs(out[-1][0] - lat_e) > 1e-7 or abs(out[-1][1] - lon_e) > 1e-7:
            out.append((lat_e, lon_e))

        deduped: List[Tuple[float, float]] = []
        for lat, lon in out:
            if not deduped or (
                abs(deduped[-1][0] - lat) > 1e-8 or abs(deduped[-1][1] - lon) > 1e-8
            ):
                deduped.append((lat, lon))
        return deduped

    def _build_path_segment_avoid_rings(
        self,
        *,
        origin: Coordinate,
        destination: Coordinate,
        max_rings: int,
    ) -> List[List[List[float]]]:
        if max_rings <= 0:
            return []

        bad_conditions = (
            PathCondition.UNEVEN,
            PathCondition.CRACKED,
            PathCondition.OBSTRUCTED,
            PathCondition.NO_SIDEWALK,
            PathCondition.UNDER_CONSTRUCTION,
        )

        mid_lat = (origin.latitude + destination.latitude) / 2.0
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * max(0.2, math.cos(math.radians(mid_lat)))
        pad = float(settings.ORS_SEGMENT_AVOID_BBOX_PAD_M)
        dlat = pad / m_per_deg_lat
        dlon = pad / m_per_deg_lon
        min_lat = min(origin.latitude, destination.latitude) - dlat
        max_lat = max(origin.latitude, destination.latitude) + dlat
        min_lon = min(origin.longitude, destination.longitude) - dlon
        max_lon = max(origin.longitude, destination.longitude) + dlon

        rows = (
            self.db.query(
                PathSegment.condition,
                func.ST_AsGeoJSON(PathSegment.geometry).label("geometry_json"),
            )
            .filter(PathSegment.condition.in_(bad_conditions))
            .all()
        )

        candidates: List[Tuple[float, float, float, float]] = []
        # (distance_to_od_chord_m, lat, lon, radius_m)
        step_m = float(settings.ORS_SEGMENT_AVOID_STEP_M)
        for row in rows:
            geom = getattr(row, "geometry_json", None)
            if not geom:
                continue
            try:
                geo = json.loads(geom)
            except (ValueError, TypeError):
                continue
            raw_coords = geo.get("coordinates")
            if not isinstance(raw_coords, list) or len(raw_coords) < 2:
                continue
            try:
                coords = [[float(p[0]), float(p[1])] for p in raw_coords]
            except (TypeError, ValueError, IndexError):
                continue

            if not self._coords_touch_route_bbox(
                coords,
                min_lat=min_lat,
                max_lat=max_lat,
                min_lon=min_lon,
                max_lon=max_lon,
            ):
                continue

            cond = row.condition
            if isinstance(cond, str):
                try:
                    cond = PathCondition(cond)
                except ValueError:
                    continue
            radius = self._ors_avoid_radius_for_path_condition(cond)

            for lat, lon in self._sample_points_along_linestring(coords, step_m):
                dist_od = self._distance_point_to_od_segment_m(
                    lat,
                    lon,
                    origin.latitude,
                    origin.longitude,
                    destination.latitude,
                    destination.longitude,
                )
                candidates.append((dist_od, lat, lon, radius))

        candidates.sort(key=lambda t: t[0])
        min_sep = float(settings.ORS_AVOID_MIN_CENTER_SEPARATION_M)
        accepted: List[Tuple[float, float, float]] = []
        for _, lat, lon, radius in candidates:
            if len(accepted) >= max_rings:
                break
            ok = True
            for alat, alon, _ in accepted:
                if self._calculate_segment_distance(lat, lon, alat, alon) < min_sep:
                    ok = False
                    break
            if ok:
                accepted.append((lat, lon, radius))

        rings: List[List[List[float]]] = []
        for lat, lon, radius in accepted:
            ring = self._circle_ring_lonlat(
                lat=lat,
                lon=lon,
                radius_meters=radius,
                points=16,
            )
            if len(ring) >= 4:
                rings.append(ring)
        return rings

    def _circle_ring_lonlat(
        self,
        *,
        lat: float,
        lon: float,
        radius_meters: float,
        points: int = 16,
    ) -> List[List[float]]:
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * max(0.2, math.cos(math.radians(lat)))
        ring: List[List[float]] = []
        for i in range(points):
            theta = (2 * math.pi * i) / points
            dlat = (radius_meters * math.sin(theta)) / meters_per_deg_lat
            dlon = (radius_meters * math.cos(theta)) / meters_per_deg_lon
            ring.append([lon + dlon, lat + dlat])
        if ring:
            ring.append(ring[0])
        return ring

    def _generate_route_coordinates(
        self, 
        origin: Coordinate, 
        destination: Coordinate,
        num_points: int = 8
    ) -> List[List[float]]:
        # Last-resort synthetic fallback when ORS and path-segment network are unavailable.
        # Keep this as a straight interpolation to avoid unrealistic artificial detours.

        coords = []
        coords.append([origin.longitude, origin.latitude])

        # Generate intermediate points by linear interpolation only.
        for i in range(1, num_points - 1):
            ratio = i / (num_points - 1)
            lat = origin.latitude + (destination.latitude - origin.latitude) * ratio
            lon = origin.longitude + (destination.longitude - origin.longitude) * ratio
            coords.append([lon, lat])

        coords.append([destination.longitude, destination.latitude])
        return coords
    
    def _calculate_route_distance(self, coordinates: List[List[float]]) -> float:
        
        # Calculate total route distance in meters
        # Uses Haversine formula for lat/lon distance calculation
        
        total_distance = 0.0
        
        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]
            
            # Haversine formula
            R = 6371000  # Earth radius in meters
            
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat / 2) ** 2 + 
                 math.cos(lat1_rad) * math.cos(lat2_rad) * 
                 math.sin(delta_lon / 2) ** 2)
            
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            
            segment_distance = R * c
            total_distance += segment_distance
        
        return total_distance
    
    def _estimate_duration(self, distance_meters: float, walking_speed: float = 1.4) -> int:
        
        # Estimate walking duration in seconds
        
        # Default walking speed: 1.4 m/s (average pedestrian)
        # Can be adjusted based on route difficulty
        
        return int(distance_meters / walking_speed)
    
    def _get_obstacles_along_route(
        self, 
        coordinates: List[List[float]],
        buffer_meters: float = 50.0
    ) -> List[ObstacleReport]:

        if len(coordinates) < 2:
            return []

        # Build a single PostGIS LineString buffer query for efficiency.
        # Coordinates are encoded as [[lon, lat], ...].
        line_wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in coordinates) + ")"

        ttl_clause = or_(
            ObstacleReport.is_temporary == False,
            ObstacleReport.created_at
            >= func.now() - text(f"interval '{settings.TEMP_OBSTACLE_TTL_HOURS} hours'"),
        )

        proximity_clause = self._route_proximity_clause(line_wkt=line_wkt, buffer_meters=buffer_meters)

        nearby = (
            self.db.query(ObstacleReport)
            .filter(
                and_(
                    ObstacleReport.is_resolved == False,
                    ObstacleReport.is_verified == True,
                    ttl_clause,
                    proximity_clause,
                )
            )
            .all()
        )

        return nearby

    def _route_proximity_clause(self, *, line_wkt: str, buffer_meters: float):
        return func.ST_DWithin(
            cast(ObstacleReport.location, Geography),
            cast(func.ST_GeomFromText(line_wkt, 4326), Geography),
            buffer_meters,
        )

    def _build_obstacle_diagnostics(
        self,
        *,
        coordinates: List[List[float]],
        buffer_meters: float,
        eligible_obstacles: List[ObstacleReport],
    ) -> RouteObstacleDiagnostics:
        if len(coordinates) < 2:
            return RouteObstacleDiagnostics(
                buffer_meters=buffer_meters,
                nearby_raw_count=0,
                excluded_resolved_count=0,
                excluded_unverified_count=0,
                excluded_expired_temporary_count=0,
                eligible_count=0,
                eligible_obstacle_yes_count=0,
                eligible_obstacle_no_count=0,
                notes=["Route had fewer than 2 points; no proximity query was performed."],
            )

        line_wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in coordinates) + ")"
        proximity_clause = self._route_proximity_clause(line_wkt=line_wkt, buffer_meters=buffer_meters)
        raw_nearby = self.db.query(ObstacleReport).filter(proximity_clause).all()

        now_utc = datetime.utcnow()
        ttl_cutoff = now_utc - timedelta(hours=settings.TEMP_OBSTACLE_TTL_HOURS)

        excluded_resolved_count = 0
        excluded_unverified_count = 0
        excluded_expired_temporary_count = 0

        for obs in raw_nearby:
            if obs.is_resolved:
                excluded_resolved_count += 1
                continue
            if not obs.is_verified:
                excluded_unverified_count += 1
                continue
            created_at = obs.created_at
            if created_at is not None and created_at.tzinfo is not None:
                # Normalize aware timestamps to naive UTC before comparison.
                created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            if (
                obs.is_temporary
                and created_at is not None
                and created_at < ttl_cutoff
            ):
                excluded_expired_temporary_count += 1

        eligible_obstacle_yes_count = sum(
            1 for obs in eligible_obstacles if obs.obstacle_type == ObstacleType.YES
        )
        eligible_obstacle_no_count = sum(
            1 for obs in eligible_obstacles if obs.obstacle_type == ObstacleType.NO
        )

        notes: List[str] = []
        if len(eligible_obstacles) == 0:
            notes.append("No eligible obstacles matched all filters near this route.")
        if len(raw_nearby) == 0:
            notes.append("No obstacle reports were found within the route buffer.")
        if excluded_unverified_count > 0:
            notes.append(
                f"{excluded_unverified_count} nearby report(s) excluded because they are not verified."
            )
        if excluded_resolved_count > 0:
            notes.append(
                f"{excluded_resolved_count} nearby report(s) excluded because they are resolved."
            )
        if excluded_expired_temporary_count > 0:
            notes.append(
                f"{excluded_expired_temporary_count} nearby report(s) excluded due to temporary-obstacle TTL."
            )
        if eligible_obstacle_no_count > 0 and eligible_obstacle_yes_count == 0:
            notes.append(
                "Eligible nearby reports are labeled obstacle_type='no'; these do not produce obstacle warnings."
            )

        return RouteObstacleDiagnostics(
            buffer_meters=buffer_meters,
            nearby_raw_count=len(raw_nearby),
            excluded_resolved_count=excluded_resolved_count,
            excluded_unverified_count=excluded_unverified_count,
            excluded_expired_temporary_count=excluded_expired_temporary_count,
            eligible_count=len(eligible_obstacles),
            eligible_obstacle_yes_count=eligible_obstacle_yes_count,
            eligible_obstacle_no_count=eligible_obstacle_no_count,
            notes=notes,
        )
    
    def _subtype_penalty_multiplier(self, subtype: Optional[ObstacleSubtype]) -> float:
        if subtype is None:
            return 1.0
        if subtype in (
            ObstacleSubtype.FLOODING,
            ObstacleSubtype.STAIRS_ONLY,
            ObstacleSubtype.MISSING_CURB_CUT,
        ):
            return 1.8
        if subtype in (
            ObstacleSubtype.PARKED_VEHICLE,
            ObstacleSubtype.VENDOR_STALL,
            ObstacleSubtype.CONSTRUCTION,
        ):
            return 1.3
        if subtype in (
            ObstacleSubtype.BROKEN_PAVEMENT,
            ObstacleSubtype.UNEVEN_SURFACE,
        ):
            return 1.1
        return 1.0

    def _calculate_accessibility_score(
        self,
        coordinates: List[List[float]],
        obstacles: List[ObstacleReport],
        request: RouteRequest,
        user: Optional[User] = None
    ) -> float:

        # Calculate accessibility score (0.0 - 1.0). Higher = more accessible.
        #
        # Per-segment penalties: a route that threads through several legs next to the
        # same hazard (or multiple hazards) must score worse than a detour that stays
        # clear. Flat "once per obstacle" scoring made every ORS candidate tie, so the
        # shortest geometry always won even when steps showed many uneven legs.

        score = 1.0
        yes_obs = [o for o in obstacles if o.obstacle_type == ObstacleType.YES]
        near_m = float(settings.ROUTE_SCORE_OBSTACLE_NEAR_LEG_M)
        want_smooth = bool(request.require_smooth_pavement) or bool(
            user is not None and user.require_smooth_pavement
        )
        amplify = (
            float(settings.ROUTE_SCORE_SMOOTH_PAVEMENT_AMPLIFY) if want_smooth else 1.0
        )

        if len(coordinates) >= 2 and yes_obs:
            for i in range(len(coordinates) - 1):
                lon1, lat1 = coordinates[i]
                lon2, lat2 = coordinates[i + 1]
                min_d = float("inf")
                closest: Optional[ObstacleReport] = None
                for o in yes_obs:
                    d = self._distance_obstacle_to_segment_m(
                        o, lat1, lon1, lat2, lon2
                    )
                    if d < min_d:
                        min_d = d
                        closest = o
                if closest is None or min_d >= near_m:
                    continue
                proximity = 1.0 - (min_d / near_m)
                # Up to ~0.11 off per leg at severity 5, d=0, before subtype + amplify.
                leg = (
                    (closest.severity / 5.0)
                    * 0.11
                    * self._subtype_penalty_multiplier(closest.report_subtype)
                    * proximity
                    * amplify
                )
                score -= leg

        score = max(0.0, min(1.0, score))
        return round(score, 2)
    
    def _generate_route_steps(
        self,
        coordinates: List[List[float]],
        obstacles: List[ObstacleReport]
    ) -> List[RouteStep]:
        
        # Generate turn-by-turn navigation steps
        
        # Creates human-readable navigation instructions
        
        steps = []
        segment_count = len(coordinates) - 1
        on_path_m = 12.0
        near_hazard_m = float(settings.ROUTE_SCORE_OBSTACLE_NEAR_LEG_M)
        yes_obs = [o for o in obstacles if o.obstacle_type == ObstacleType.YES]

        # Assign each obstacle only to its nearest local segment(s), instead of
        # letting every segment independently "see" the same obstacle.
        # This keeps highlights tightly localized.
        segment_obstacle_map: Dict[int, Tuple[ObstacleReport, float]] = {}
        for obs in obstacles:
            distances: List[Tuple[int, float]] = []
            for i in range(segment_count):
                lon1, lat1 = coordinates[i]
                lon2, lat2 = coordinates[i + 1]
                d = self._distance_obstacle_to_segment_m(obs, lat1, lon1, lat2, lon2)
                distances.append((i, d))
            if not distances:
                continue
            distances.sort(key=lambda x: x[1])
            best_distance = distances[0][1]
            if best_distance > on_path_m:
                continue

            # Allow spillover to at most one adjacent/near-tied segment only.
            candidate_segments = [distances[0]]
            if len(distances) > 1:
                second_idx, second_dist = distances[1]
                if second_dist <= on_path_m and second_dist <= best_distance + 2.5:
                    candidate_segments.append((second_idx, second_dist))

            for seg_idx, seg_dist in candidate_segments:
                existing = segment_obstacle_map.get(seg_idx)
                if existing is None or seg_dist < existing[1]:
                    segment_obstacle_map[seg_idx] = (obs, seg_dist)
        
        # Calculate distance between each point
        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]
            
            # Calculate segment distance
            segment_distance = self._calculate_segment_distance(
                lat1, lon1, lat2, lon2
            )

            # Determine direction
            direction = self._get_direction(lat1, lon1, lat2, lon2)
            
            # Generate instruction
            if i == 0:
                instruction = f"Head {direction}"
            else:
                instruction = f"Continue {direction} for {int(segment_distance)}m"
            
            # Determine path condition (simplified)
            path_condition = PathCondition.SMOOTH  # Default
            
            assigned = segment_obstacle_map.get(i)
            if assigned is not None:
                nearest_obstacle = assigned[0]
                path_condition = self._path_condition_from_obstacle(nearest_obstacle)
                instruction += f" (⚠️ {nearest_obstacle.obstacle_type.value} reported ahead)"
            elif yes_obs and near_hazard_m > on_path_m:
                # Align map visuals with score penalties: show an amber "near hazard"
                # band for hazards that are close enough to affect score but not close
                # enough to be treated as on-segment impediments.
                min_yes_dist = float("inf")
                for o in yes_obs:
                    d = self._distance_obstacle_to_segment_m(o, lat1, lon1, lat2, lon2)
                    if d < min_yes_dist:
                        min_yes_dist = d
                if on_path_m < min_yes_dist <= near_hazard_m:
                    path_condition = PathCondition.NEAR_HAZARD
                    instruction += " (⚠️ nearby reported hazard)"
            
            step = RouteStep(
                distance=segment_distance,
                duration=0,
                instruction=instruction,
                path_condition=path_condition,
            )
            
            steps.append(step)
        
        # Add final step
        steps.append(RouteStep(
            distance=0,
            duration=0,
            instruction="You have arrived at your destination",
            path_condition=PathCondition.SMOOTH
        ))
        
        return steps

    def _path_condition_from_obstacle(self, obstacle: ObstacleReport) -> PathCondition:
        # Map report metadata to user-facing step condition.
        if obstacle.report_kind == "surface_problem":
            return PathCondition.UNEVEN
        if obstacle.report_subtype in (
            ObstacleSubtype.BROKEN_PAVEMENT,
            ObstacleSubtype.UNEVEN_SURFACE,
        ):
            return PathCondition.UNEVEN
        if obstacle.report_subtype in (
            ObstacleSubtype.STAIRS_ONLY,
            ObstacleSubtype.MISSING_CURB_CUT,
        ):
            return PathCondition.NO_SIDEWALK
        return PathCondition.OBSTRUCTED
    
    def _calculate_segment_distance(
        self, 
        lat1: float, lon1: float, 
        lat2: float, lon2: float
    ) -> float:
        
        # Calculate distance between two points in meters
        
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _get_direction(
        self, 
        lat1: float, lon1: float, 
        lat2: float, lon2: float
    ) -> str:
        
        # Calculate compass direction between two points
        # Returns: north, south, east, west, northeast, etc.
        
        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1
        
        # Calculate bearing
        bearing = math.atan2(delta_lon, delta_lat)
        bearing_degrees = math.degrees(bearing)
        
        # Normalize to 0-360
        bearing_degrees = (bearing_degrees + 360) % 360
        
        # Convert to compass direction
        directions = [
            "north", "northeast", "east", "southeast",
            "south", "southwest", "west", "northwest"
        ]
        
        index = int((bearing_degrees + 22.5) / 45) % 8
        
        return directions[index]
    
    def _is_obstacle_near_segment(
        self,
        obstacle: ObstacleReport,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        threshold_meters: float = 30.0
    ) -> bool:
        dist = self._distance_obstacle_to_segment_m(obstacle, lat1, lon1, lat2, lon2)
        return dist <= threshold_meters

    def _distance_obstacle_to_segment_m(
        self,
        obstacle: ObstacleReport,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        # Project lat/lon to a local metric plane and compute
        # perpendicular distance to the actual segment.
        ox, oy = self._latlon_to_local_xy(obstacle.latitude, obstacle.longitude, lat1)
        x1, y1 = self._latlon_to_local_xy(lat1, lon1, lat1)
        x2, y2 = self._latlon_to_local_xy(lat2, lon2, lat1)

        dx = x2 - x1
        dy = y2 - y1
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq <= 1e-6:
            return math.hypot(ox - x1, oy - y1)

        t = ((ox - x1) * dx + (oy - y1) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        px = x1 + t * dx
        py = y1 + t * dy
        return math.hypot(ox - px, oy - py)

    def _latlon_to_local_xy(self, lat: float, lon: float, ref_lat: float) -> Tuple[float, float]:
        # Equirectangular projection around reference latitude.
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * math.cos(math.radians(ref_lat))
        return lon * meters_per_deg_lon, lat * meters_per_deg_lat
    
    def _generate_warnings(
        self,
        request: RouteRequest,
        obstacles: List[ObstacleReport],
        user: Optional[User] = None
    ) -> List[str]:
        
        # Generate warnings about route accessibility issues
        
        # Warns user about:
        # - Obstacles that conflict with preferences
        # - High-severity obstacles
        # - Missing accessibility features
        
        warnings = []
        
        # Check for generic obstacle warnings in binary obstacle mode.
        for obs in obstacles:
            subtype_label = (
                obs.report_subtype.value.replace("_", " ")
                if obs.report_subtype is not None
                else "obstacle"
            )
            if obs.obstacle_type == ObstacleType.YES:
                warnings.append(f"Route contains reported {subtype_label}")
            
            # High severity obstacles
            if obs.severity >= 4:
                warnings.append(f"High-severity {subtype_label} ahead")
        
        # Limit warnings
        if len(warnings) > 5:
            warnings = warnings[:5]
            warnings.append(f"...and {len(obstacles) - 5} more obstacles")
        
        return warnings