from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


# Enums
class AccessibilityType(str, Enum):
    VISUALLY_IMPAIRED = "visually_impaired"
    MOVEMENT_IMPAIRED = "movement_impaired"
    STANDARD_PEDESTRIAN = "standard_pedestrian"


class PathCondition(str, Enum):
    SMOOTH = "smooth"
    CRACKED = "cracked"
    UNEVEN = "uneven"
    OBSTRUCTED = "obstructed"
    NO_SIDEWALK = "no_sidewalk"
    UNDER_CONSTRUCTION = "under_construction"


class ObstacleType(str, Enum):
    VENDOR_STALL = "vendor_stall"
    PARKED_VEHICLE = "parked_vehicle"
    CONSTRUCTION = "construction"
    BROKEN_PAVEMENT = "broken_pavement"
    FLOODING = "flooding"
    STEEP_INCLINE = "steep_incline"
    STAIRS = "stairs"
    NO_CURB_CUT = "no_curb_cut"
    OTHER = "other"


# User Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    accessibility_type: AccessibilityType = AccessibilityType.STANDARD_PEDESTRIAN


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    accessibility_type: Optional[AccessibilityType] = None
    avoid_stairs: Optional[bool] = None
    avoid_steep_inclines: Optional[bool] = None
    require_curb_cuts: Optional[bool] = None
    require_smooth_pavement: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    accessibility_type: AccessibilityType
    avoid_stairs: bool
    avoid_steep_inclines: bool
    require_curb_cuts: bool
    require_smooth_pavement: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Route Schemas
class Coordinate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    avoid_stairs: Optional[bool] = None
    avoid_steep_inclines: Optional[bool] = None
    require_curb_cuts: Optional[bool] = None
    require_smooth_pavement: Optional[bool] = None


class RouteStep(BaseModel):
    distance: float
    duration: int
    instruction: str
    path_condition: Optional[PathCondition] = None


class RouteResponse(BaseModel):
    id: Optional[int] = None
    distance_meters: float
    estimated_duration_seconds: int
    accessibility_score: float
    coordinates: List[List[float]]  # [[lon, lat], [lon, lat], ...]
    steps: List[RouteStep]
    warnings: List[str] = []


# Obstacle Schemas
class ObstacleReportCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    obstacle_type: ObstacleType
    description: Optional[str] = None
    severity: int = Field(default=3, ge=1, le=5)
    is_temporary: bool = True


class ObstacleReportResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    obstacle_type: ObstacleType
    description: Optional[str]
    severity: int
    is_temporary: bool
    is_verified: bool
    is_resolved: bool
    image_url: Optional[str]
    created_at: datetime
    reporter_id: int
    
    model_config = ConfigDict(from_attributes=True)


# Path Validation Schemas
class PathValidationCreate(BaseModel):
    latitude: float
    longitude: float
    is_passable: bool
    reported_condition: Optional[PathCondition] = None
    notes: Optional[str] = None


# LGU Report Schemas
class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    severity: float
    obstacle_count: int


class LGUReportResponse(BaseModel):
    report_date: datetime
    total_obstacles: int
    unresolved_obstacles: int
    high_severity_count: int
    heatmap_points: List[HeatmapPoint]
    csv_download_url: Optional[str] = None