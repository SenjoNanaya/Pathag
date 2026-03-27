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
    NEAR_HAZARD = "near_hazard"
    OBSTRUCTED = "obstructed"
    NO_SIDEWALK = "no_sidewalk"
    UNDER_CONSTRUCTION = "under_construction"


class ObstacleType(str, Enum):
    YES = "yes"
    NO = "no"


class ReportKind(str, Enum):
    OBSTACLE = "obstacle"
    SURFACE_PROBLEM = "surface_problem"
    ENVIRONMENTAL = "environmental"


class ObstacleSubtype(str, Enum):
    PARKED_VEHICLE = "parked_vehicle"
    VENDOR_STALL = "vendor_stall"
    CONSTRUCTION = "construction"
    FLOODING = "flooding"
    BROKEN_PAVEMENT = "broken_pavement"
    UNEVEN_SURFACE = "uneven_surface"
    MISSING_CURB_CUT = "missing_curb_cut"
    STAIRS_ONLY = "stairs_only"
    OTHER = "other"


class SubtypeSource(str, Enum):
    USER = "user"
    ML_SUGGESTED = "ml_suggested"


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
    duration: int = 0
    instruction: str
    path_condition: Optional[PathCondition] = None


class RouteObstacleDiagnostics(BaseModel):
    buffer_meters: float
    nearby_raw_count: int
    excluded_resolved_count: int
    excluded_unverified_count: int
    excluded_expired_temporary_count: int
    eligible_count: int
    eligible_obstacle_yes_count: int
    eligible_obstacle_no_count: int
    notes: List[str] = []


class RouteAlternativeResponse(BaseModel):
    distance_meters: float
    estimated_duration_seconds: int
    accessibility_score: float
    coordinates: List[List[float]]
    steps: List[RouteStep]
    warnings: List[str] = []
    force_not_recommended: bool = False
    not_recommended_reasons: List[str] = []


class RouteResponse(BaseModel):
    id: Optional[int] = None
    distance_meters: float
    estimated_duration_seconds: int
    accessibility_score: float
    coordinates: List[List[float]]  # [[lon, lat], [lon, lat], ...]
    steps: List[RouteStep]
    warnings: List[str] = []
    obstacle_diagnostics: Optional[RouteObstacleDiagnostics] = None
    alternative_routes: List[RouteAlternativeResponse] = Field(default_factory=list)


# Obstacle Schemas
class ObstacleReportCreate(BaseModel):
    reporter_id: Optional[int] = Field(
        default=None,
        description="Optional logged-in user; omit for anonymous reports (DB column is nullable).",
    )
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    obstacle_type: ObstacleType
    report_kind: ReportKind = ReportKind.OBSTACLE
    report_subtype: ObstacleSubtype = ObstacleSubtype.OTHER
    subtype_source: SubtypeSource = SubtypeSource.USER
    description: Optional[str] = None
    severity: int = Field(default=3, ge=1, le=5)
    is_temporary: bool = True


class ObstacleVerificationCreate(BaseModel):
    verifier_id: int
    notes: Optional[str] = None


class ObstacleResolveCreate(BaseModel):
    resolver_id: int


class ObstacleVerificationTemplate(BaseModel):
    verifier_id: int = 1
    notes: Optional[str] = "Admin verification"


class ObstacleResolveTemplate(BaseModel):
    resolver_id: int = 1


class ObstacleReportResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    obstacle_type: ObstacleType
    report_kind: ReportKind
    report_subtype: ObstacleSubtype
    subtype_source: SubtypeSource
    description: Optional[str]
    severity: int
    is_temporary: bool
    is_verified: bool
    is_resolved: bool
    image_url: Optional[str]
    created_at: datetime
    reporter_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class AdminObstacleReportResponse(ObstacleReportResponse):
    verification_count: int = 0
    verify_endpoint: str
    resolve_endpoint: str
    unresolve_endpoint: str
    verify_request_body: ObstacleVerificationTemplate
    resolve_request_body: ObstacleResolveTemplate
    unresolve_request_body: ObstacleResolveTemplate


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
    subtype_counts: dict[str, int] = Field(default_factory=dict)


class LGUReportResponse(BaseModel):
    report_date: datetime
    total_obstacles: int
    unresolved_obstacles: int
    high_severity_count: int
    heatmap_points: List[HeatmapPoint]
    csv_download_url: Optional[str] = None
    # Planning-oriented rollups (all unresolved in bbox, not only heatmap-filtered cells).
    subtype_breakdown: dict[str, int] = Field(default_factory=dict)
    report_kind_breakdown: dict[str, int] = Field(default_factory=dict)


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


class LGUPlanningExportRequest(BaseModel):
    """
    GIS / maintenance exports for a bounding box (campus, barangay, project corridor).

    Typical workflow: export GeoJSON → QGIS/ArcGIS; join to road/path layers;
    filter `workflow_status=confirmed_open` and `severity>=4` for capital works backlog.
    """

    min_latitude: float = Field(..., ge=-90, le=90)
    min_longitude: float = Field(..., ge=-180, le=180)
    max_latitude: float = Field(..., ge=-90, le=90)
    max_longitude: float = Field(..., ge=-180, le=180)

    only_verified: bool = Field(
        default=True,
        description="If true, only reports that passed verification (same bar as routing).",
    )
    include_resolved: bool = Field(
        default=False,
        description="If false, export only open issues (default for maintenance backlogs).",
    )
    min_severity: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Optional floor severity (e.g. 4 for high-priority lists).",
    )
    respect_temporary_ttl: bool = Field(
        default=True,
        description="Exclude expired temporary reports when true (matches live map TTL).",
    )


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
    obstruction_yes_probability: Optional[float] = None
    obstacle_yes: bool
    obstacle: Optional[ObstacleClassificationResponse] = None
