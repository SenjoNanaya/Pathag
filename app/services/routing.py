"""
Routing Service - Accessibility-Aware Pathfinding
Calculates routes with accessibility scoring and user preference application
"""
import math
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Point
from geoalchemy2.elements import WKTElement

from app.models.models import PathSegment, ObstacleReport, User, PathCondition, ObstacleType
from app.schemas.schemas import RouteRequest, RouteResponse, RouteStep, Coordinate


class RoutingService:    
    def __init__(self, db: Session):
        self.db = db
    
    async def calculate_route(
        self, 
        request: RouteRequest,
        user: Optional[User] = None
    ) -> RouteResponse:
        # Calculate an accessible route between two points
        
        # 1. Generate base route coordinates
        # 2. Check for obstacles along route
        # 3. Calculate accessibility score
        # 4. Apply user preferences
        # 5. Generate turn-by-turn steps
        # 6. Create warnings if needed
        # Generate base route (simplified demo routing)

        coordinates = self._generate_route_coordinates(
            request.origin, 
            request.destination
        )
        
        # Calculate distance and duration
        distance = self._calculate_route_distance(coordinates)
        duration = self._estimate_duration(distance)
        
        # Get obstacles along route
        obstacles = self._get_obstacles_along_route(coordinates)
        
        # Calculate accessibility score
        accessibility_score = self._calculate_accessibility_score(
            coordinates,
            obstacles,
            request,
            user
        )
        
        # Generate navigation steps
        steps = self._generate_route_steps(coordinates, obstacles)
        
        # Generate warnings
        warnings = self._generate_warnings(request, obstacles, user)
        
        return RouteResponse(
            distance_meters=distance,
            estimated_duration_seconds=duration,
            accessibility_score=accessibility_score,
            coordinates=coordinates,
            steps=steps,
            warnings=warnings
        )
    
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
        
        # Get obstacles near the route
        
        # Uses PostGIS to find obstacles within buffer distance of route
        
        obstacles = []
        
        # Check obstacles near each coordinate
        for lon, lat in coordinates:
            # Create point geometry
            point = f'POINT({lon} {lat})'
            
            # Query obstacles within buffer
            nearby = self.db.query(ObstacleReport).filter(
                and_(
                    ObstacleReport.is_resolved == False,
                    func.ST_DWithin(
                        ObstacleReport.location,
                        func.ST_GeomFromText(point, 4326),
                        buffer_meters
                    )
                )
            ).all()
            
            obstacles.extend(nearby)
        
        # Remove duplicates
        seen = set()
        unique_obstacles = []
        for obs in obstacles:
            if obs.id not in seen:
                seen.add(obs.id)
                unique_obstacles.append(obs)
        
        return unique_obstacles
    
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
            
            # Increased penalty if obstacle type conflicts with user prefs
            if user or request:
                # Check user preferences
                avoid_stairs = (user and user.avoid_stairs) or request.avoid_stairs
                avoid_inclines = (user and user.avoid_steep_inclines) or request.avoid_steep_inclines
                
                if avoid_stairs and obstacle.obstacle_type == ObstacleType.STAIRS:
                    penalty *= 2.0  # Double penalty
                
                if avoid_inclines and obstacle.obstacle_type == ObstacleType.STEEP_INCLINE:
                    penalty *= 1.5
            
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
        
        # Get user preferences
        avoid_stairs = (user and user.avoid_stairs) or request.avoid_stairs
        avoid_inclines = (user and user.avoid_steep_inclines) or request.avoid_steep_inclines
        require_curb_cuts = (user and user.require_curb_cuts) or request.require_curb_cuts
        
        # Check for preference violations
        for obs in obstacles:
            if avoid_stairs and obs.obstacle_type == ObstacleType.STAIRS:
                warnings.append(f"Route contains stairs at ({obs.latitude:.4f}, {obs.longitude:.4f})")
            
            if avoid_inclines and obs.obstacle_type == ObstacleType.STEEP_INCLINE:
                warnings.append(f"Route contains steep incline")
            
            if require_curb_cuts and obs.obstacle_type == ObstacleType.NO_CURB_CUT:
                warnings.append(f"Missing curb cut reported on route")
            
            # High severity obstacles
            if obs.severity >= 4:
                warnings.append(f"High-severity obstacle: {obs.obstacle_type.value}")
        
        # Limit warnings
        if len(warnings) > 5:
            warnings = warnings[:5]
            warnings.append(f"...and {len(obstacles) - 5} more obstacles")
        
        return warnings