"""
Routing Service - Accessibility-Aware Pathfinding
Calculates routes with accessibility scoring and user preference application
"""
import math
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Point
from geoalchemy2.elements import WKTElement

import httpx

from app.models.models import PathSegment, ObstacleReport, User, PathCondition, ObstacleType
from app.config import settings
from app.schemas.schemas import RouteRequest, RouteResponse, RouteStep, Coordinate


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
        best_score = -1.0

        # 2) Score each candidate by accessibility and select the best.
        for coordinates in route_candidates:
            obstacles = self._get_obstacles_along_route(coordinates, buffer_meters=settings.OBSTACLE_ROUTE_BUFFER_METERS)
            accessibility_score = self._calculate_accessibility_score(
                coordinates=coordinates,
                obstacles=obstacles,
                request=request,
                user=user,
            )
            if accessibility_score > best_score:
                best_score = accessibility_score
                best = {
                    "coordinates": coordinates,
                    "obstacles": obstacles,
                }

        assert best is not None  # for type-checkers; route_candidates always has >= 1
        coordinates = best["coordinates"]
        obstacles = best["obstacles"]

        # 3) Final metrics for the selected route.
        distance = self._calculate_route_distance(coordinates)
        duration = self._estimate_duration(distance)
        steps = self._generate_route_steps(coordinates, obstacles)
        warnings = self._generate_warnings(request, obstacles, user)

        return RouteResponse(
            distance_meters=distance,
            estimated_duration_seconds=duration,
            accessibility_score=best_score,
            coordinates=coordinates,
            steps=steps,
            warnings=warnings,
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
                if coords_list:
                    return coords_list
            except Exception:
                # ORS issues should not take down the entire routing service.
                pass

        # Fallback: simplified demo routing (single candidate).
        return [self._generate_route_coordinates(origin, destination)]

    async def _fetch_ors_route_alternatives(
        self,
        origin: Coordinate,
        destination: Coordinate,
    ) -> List[List[List[float]]]:
        """
        Calls OpenRouteService directions endpoint and returns alternative geometries.

        The response structure can vary by ORS version/settings; parsing is defensive.
        """

        url = f"{settings.ORS_BASE_URL}/directions/{settings.ORS_PROFILE}"
        headers = {"Authorization": settings.ORS_API_KEY}
        payload = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "alternatives": settings.ORS_ALTERNATIVES,
            "instructions": False,
            # Ask ORS to include geometry so we can score obstacle impact along it.
            "geometry": True,
        }

        async with httpx.AsyncClient(timeout=settings.ORS_REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        routes = data.get("routes") or []
        coords_list: List[List[List[float]]] = []
        for route in routes:
            geom = route.get("geometry")
            if not geom:
                continue
            # ORS often returns geojson: {"type":"LineString","coordinates":[...]}
            if isinstance(geom, dict) and "coordinates" in geom:
                coords = geom["coordinates"]
            # Sometimes ORS returns geometry as a raw coordinate list.
            elif isinstance(geom, list):
                coords = geom
            else:
                continue

            if coords:
                coords_list.append([[float(lon), float(lat)] for lon, lat in coords])

        return coords_list

    def _generate_route_coordinates(
        self, 
        origin: Coordinate, 
        destination: Coordinate,
        num_points: int = 8
    ) -> List[List[float]]:
        
        # Generate route coordinates (simplified demo routing)

        coords = []
        
        # Add origin
        coords.append([origin.longitude, origin.latitude])
        
        # Generate intermediate points
        # We create a slightly curved path to simulate realistic routing
        for i in range(1, num_points - 1):
            ratio = i / (num_points - 1)
            
            # Linear interpolation
            lat = origin.latitude + (destination.latitude - origin.latitude) * ratio
            lon = origin.longitude + (destination.longitude - origin.longitude) * ratio
            
            # Add slight curve to make it more realistic
            # Offset perpendicular to the route
            if i % 2 == 0:
                curve_offset = 0.0001  # Small offset
                lat += curve_offset
            
            coords.append([lon, lat])
        
        # Add destination
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

        nearby = (
            self.db.query(ObstacleReport)
            .filter(
                and_(
                    ObstacleReport.is_resolved == False,
                    ObstacleReport.is_verified == True,
                    ttl_clause,
                    func.ST_DWithin(
                        ObstacleReport.location,
                        func.ST_GeomFromText(line_wkt, 4326),
                        buffer_meters,
                    ),
                )
            )
            .all()
        )

        return nearby
    
    def _calculate_accessibility_score(
        self,
        coordinates: List[List[float]],
        obstacles: List[ObstacleReport],
        request: RouteRequest,
        user: Optional[User] = None
    ) -> float:

        # Calculate accessibility score (0.0 - 1.0)
        
        # Score factors:
        # - Base score: 1.0 (perfect)
        # - Obstacles: -0.05 to -0.3 per obstacle (based on severity)
        # - User preferences: Additional penalties for violations
        
        # Higher score = more accessible
        
        score = 1.0
        
        # Penalty for obstacles
        for obstacle in obstacles:
            # Base penalty by severity (1-5)
            penalty = obstacle.severity * 0.05
            
            # Binary obstacle labels no longer encode obstacle subtype severity hints.
            # Keep a uniform penalty and rely on report severity + verification status.
            
            score -= penalty
        
        # Ensure score stays in valid range
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
        
        # Calculate distance between each point
        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]
            
            # Calculate segment distance
            segment_distance = self._calculate_segment_distance(
                lat1, lon1, lat2, lon2
            )
            
            # Calculate segment duration
            segment_duration = int(segment_distance / 1.4)  # 1.4 m/s walking speed
            
            # Determine direction
            direction = self._get_direction(lat1, lon1, lat2, lon2)
            
            # Generate instruction
            if i == 0:
                instruction = f"Head {direction}"
            else:
                instruction = f"Continue {direction} for {int(segment_distance)}m"
            
            # Determine path condition (simplified)
            path_condition = PathCondition.SMOOTH  # Default
            
            # Check for obstacles near this segment
            for obs in obstacles:
                if self._is_obstacle_near_segment(obs, lat1, lon1, lat2, lon2):
                    path_condition = PathCondition.OBSTRUCTED
                    instruction += f" (⚠️ {obs.obstacle_type.value} reported ahead)"
                    break
            
            step = RouteStep(
                distance=segment_distance,
                duration=segment_duration,
                instruction=instruction,
                path_condition=path_condition
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
        
        # Check if obstacle is near a route segment
        
        # Simplified: check distance to both segment endpoints
        dist1 = self._calculate_segment_distance(
            obstacle.latitude, obstacle.longitude,
            lat1, lon1
        )
        dist2 = self._calculate_segment_distance(
            obstacle.latitude, obstacle.longitude,
            lat2, lon2
        )
        
        return min(dist1, dist2) < threshold_meters
    
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
            if obs.obstacle_type == ObstacleType.YES:
                warnings.append("Route contains reported obstacle(s)")
            
            # High severity obstacles
            if obs.severity >= 4:
                warnings.append(f"High-severity obstacle: {obs.obstacle_type.value}")
        
        # Limit warnings
        if len(warnings) > 5:
            warnings = warnings[:5]
            warnings.append(f"...and {len(obstacles) - 5} more obstacles")
        
        return warnings