from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
import enum

from app.database import Base


class AccessibilityType(str, enum.Enum):
    VISUALLY_IMPAIRED = "visually_impaired"
    MOVEMENT_IMPAIRED = "movement_impaired"
    STANDARD_PEDESTRIAN = "standard_pedestrian"


class PathCondition(str, enum.Enum):
    SMOOTH = "smooth"
    CRACKED = "cracked"
    UNEVEN = "uneven"
    OBSTRUCTED = "obstructed"
    NO_SIDEWALK = "no_sidewalk"
    UNDER_CONSTRUCTION = "under_construction"


class ObstacleType(str, enum.Enum):
    YES = "yes"
    NO = "no"


class ReportKind(str, enum.Enum):
    OBSTACLE = "obstacle"
    SURFACE_PROBLEM = "surface_problem"
    ENVIRONMENTAL = "environmental"


class ObstacleSubtype(str, enum.Enum):
    PARKED_VEHICLE = "parked_vehicle"
    VENDOR_STALL = "vendor_stall"
    CONSTRUCTION = "construction"
    FLOODING = "flooding"
    BROKEN_PAVEMENT = "broken_pavement"
    UNEVEN_SURFACE = "uneven_surface"
    MISSING_CURB_CUT = "missing_curb_cut"
    STAIRS_ONLY = "stairs_only"
    OTHER = "other"


class SubtypeSource(str, enum.Enum):
    USER = "user"
    ML_SUGGESTED = "ml_suggested"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    accessibility_type = Column(Enum(AccessibilityType), default=AccessibilityType.STANDARD_PEDESTRIAN)
    
    # User preferences (stored as JSON-like structure)
    avoid_stairs = Column(Boolean, default=False)
    avoid_steep_inclines = Column(Boolean, default=False)
    require_curb_cuts = Column(Boolean, default=False)
    require_smooth_pavement = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    obstacle_reports = relationship("ObstacleReport", back_populates="reporter")
    obstacle_verifications = relationship("ObstacleVerification", back_populates="verifier")
    path_validations = relationship("PathValidation", back_populates="validator")


class PathSegment(Base):
    __tablename__ = "path_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Geometry - LineString representing the path segment
    geometry = Column(Geometry('LINESTRING', srid=4326), nullable=False)
    
    # Start and end coordinates (for quick queries)
    start_lat = Column(Float, nullable=False)
    start_lon = Column(Float, nullable=False)
    end_lat = Column(Float, nullable=False)
    end_lon = Column(Float, nullable=False)
    
    # Path characteristics
    condition = Column(Enum(PathCondition), default=PathCondition.SMOOTH)
    accessibility_score = Column(Float, default=1.0)  # 0.0 (inaccessible) to 1.0 (fully accessible)
    width_meters = Column(Float)
    slope_percentage = Column(Float)
    has_tactile_paving = Column(Boolean, default=False)
    has_curb_cuts = Column(Boolean, default=False)
    
    # Data source
    source = Column(String, default="manual")  # manual, cv_model, crowdsourced
    confidence_score = Column(Float, default=1.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    obstacle_reports = relationship("ObstacleReport", back_populates="path_segment")
    validations = relationship("PathValidation", back_populates="path_segment")


class ObstacleReport(Base):
    __tablename__ = "obstacle_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Location
    location = Column(Geometry('POINT', srid=4326), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Obstacle details
    obstacle_type = Column(Enum(ObstacleType), nullable=False)
    report_kind = Column(Enum(ReportKind), nullable=False, default=ReportKind.OBSTACLE)
    report_subtype = Column(Enum(ObstacleSubtype), nullable=False, default=ObstacleSubtype.OTHER)
    subtype_source = Column(Enum(SubtypeSource), nullable=False, default=SubtypeSource.USER)
    description = Column(Text)
    severity = Column(Integer, default=3)  # 1 (minor) to 5 (severe)
    is_temporary = Column(Boolean, default=True)
    
    # Image evidence
    image_url = Column(String)
    
    # Status
    is_verified = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    
    # Reporter
    reporter_id = Column(Integer, ForeignKey("users.id"))
    reporter = relationship("User", back_populates="obstacle_reports")
    
    # Associated path segment
    path_segment_id = Column(Integer, ForeignKey("path_segments.id"), nullable=True)
    path_segment = relationship("PathSegment", back_populates="obstacle_reports")

    # Human verification events (crowdsourced / moderation).
    verifications = relationship("ObstacleVerification", back_populates="obstacle_report")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


class PathValidation(Base):
    __tablename__ = "path_validations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    path_segment_id = Column(Integer, ForeignKey("path_segments.id"), nullable=False)
    path_segment = relationship("PathSegment", back_populates="validations")
    
    validator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    validator = relationship("User", back_populates="path_validations")
    
    # Validation details
    is_passable = Column(Boolean, nullable=False)
    reported_condition = Column(Enum(PathCondition))
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Route(Base):
    __tablename__ = "routes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Route geometry
    geometry = Column(Geometry('LINESTRING', srid=4326))
    
    # Origin and destination
    origin_lat = Column(Float, nullable=False)
    origin_lon = Column(Float, nullable=False)
    dest_lat = Column(Float, nullable=False)
    dest_lon = Column(Float, nullable=False)
    
    # Route metrics
    distance_meters = Column(Float)
    estimated_duration_seconds = Column(Integer)
    accessibility_score = Column(Float)
    
    # User who requested
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Cache for repeated queries
    is_cached = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ObstacleVerification(Base):
    """
    Stores individual verifier confirmations for an obstacle report.

    Route scoring uses `ObstacleReport.is_verified`, which is computed by
    counting rows in this table and comparing against
    `settings.OBSTACLE_VERIFICATION_THRESHOLD`.
    """

    __tablename__ = "obstacle_verifications"
    __table_args__ = (
        UniqueConstraint(
            "obstacle_report_id",
            "verifier_id",
            name="uq_obstacle_verifications_report_verifier",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    obstacle_report_id = Column(
        Integer, ForeignKey("obstacle_reports.id"), nullable=False, index=True
    )
    obstacle_report = relationship("ObstacleReport", back_populates="verifications")

    verifier_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    verifier = relationship("User", back_populates="obstacle_verifications")

    notes = Column(Text)

    # If you want "deny" support later, add a boolean here; for now we treat any row
    # as a "verified" confirmation.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
