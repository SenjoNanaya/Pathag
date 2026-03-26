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
    YES = "yes"
    NO = "no"


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
    reporter_id: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    obstacle_type: ObstacleType
    description: Optional[str] = None
    severity: int = Field(default=3, ge=1, le=5)
    is_temporary: bool = True


class ObstacleVerificationCreate(BaseModel):
    verifier_id: int
    notes: Optional[str] = None


class ObstacleResolveCreate(BaseModel):
    resolver_id: int


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


class LGUHeatmapRequest(BaseModel):
    """
    Bounding-box export for a given LGU (or any admin-area bounding box).

    Note: we don't store an LGU entity in the DB yet; this request is purely geometric.
    """

    min_latitude: float = Field(..., ge=-90, le=90)
    min_longitude: float = Field(..., ge=-180, le=180)
    max_latitude: float = Field(..., ge=-90, le=90)
    max_longitude: float = Field(..., ge=-180, le=180)

    # Grid cell size in meters (approx; for lat/lon conversion we use a local approximation).
    grid_cell_size_meters: float = Field(default=250.0, gt=0)

    # Only verified obstacles should influence “inaccessibility” heatmaps.
    only_verified: bool = True


# ML — path surface classification (MobileNetV3)
class PathClassificationResponse(BaseModel):
    """Transparent classifier output; not committed to live map data without verification."""

    path_condition: PathCondition
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: dict[str, float]
    narrative_reasons: List[str]
    checkpoint_loaded: bool
    eligible_for_live_map: bool = False


# ML — obstacle-type classification (MobileNetV3)
class ObstacleClassificationResponse(BaseModel):
    """
    Transparent classifier output; obstacle classification must not be used to write live map data
    without human verification.
    """

    obstacle_type: ObstacleType
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: dict[str, float]
    narrative_reasons: List[str]
    checkpoint_loaded: bool
    eligible_for_live_map: bool = False
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
    YES = "yes"
    NO = "no"


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
    reporter_id: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    obstacle_type: ObstacleType
    description: Optional[str] = None
    severity: int = Field(default=3, ge=1, le=5)
    is_temporary: bool = True


class ObstacleVerificationCreate(BaseModel):
    verifier_id: int
    notes: Optional[str] = None


class ObstacleResolveCreate(BaseModel):
    resolver_id: int


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


class LGUHeatmapRequest(BaseModel):
    """
    Bounding-box export for a given LGU (or any admin-area bounding box).

    Note: we don't store an LGU entity in the DB yet; this request is purely geometric.
    """

    min_latitude: float = Field(..., ge=-90, le=90)
    min_longitude: float = Field(..., ge=-180, le=180)
    max_latitude: float = Field(..., ge=-90, le=90)
    max_longitude: float = Field(..., ge=-180, le=180)

    # Grid cell size in meters (approx; for lat/lon conversion we use a local approximation).
    grid_cell_size_meters: float = Field(default=250.0, gt=0)

    # Only verified obstacles should influence “inaccessibility” heatmaps.
    only_verified: bool = True


# ML — path surface classification (MobileNetV3)
class PathClassificationResponse(BaseModel):
    """Transparent classifier output; not committed to live map data without verification."""

    path_condition: PathCondition
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: dict[str, float]
    narrative_reasons: List[str]
    checkpoint_loaded: bool
    eligible_for_live_map: bool = False


# ML — obstacle-type classification (MobileNetV3)
class ObstacleClassificationResponse(BaseModel):
    """
    Transparent classifier output; obstacle classification must not be used to write live map data
    without human verification.
    """

    obstacle_type: ObstacleType
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: dict[str, float]
    narrative_reasons: List[str]
    checkpoint_loaded: bool
    eligible_for_live_map: bool = False


# Combined ML response for a single uploaded image.
class CombinedImageClassificationResponse(BaseModel):
    """
    Run both models (path surface condition + obstacle type) on the same image.
    """

    path: PathClassificationResponse
    obstruction_present_probability: Optional[float] = None
    obstacle_present: bool
    obstacle: Optional[ObstacleClassificationResponse] = None
