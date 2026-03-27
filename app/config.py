from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://pathag:pathag@localhost:5432/pathag"
    # Supabase and most cloud Postgres require TLS. Set true on Render if the URL has no sslmode=.
    DATABASE_SSL_REQUIRE: bool = False
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OpenRouteService API
    ORS_API_KEY: Optional[str] = None
    ORS_BASE_URL: str = "https://api.openrouteservice.org/v2"
    ORS_PROFILE: str = "foot-walking"
    ORS_ALTERNATIVES: int = 3
    ORS_REQUEST_TIMEOUT_SECONDS: int = 30
    # Hard avoid zones for ORS (verified reports + mapped poor path_segments).
    ORS_AVOID_REPORT_RADIUS_M: float = 14.0
    ORS_AVOID_MAX_TOTAL_POLYGONS: int = 100
    ORS_SEGMENT_AVOID_ENABLED: bool = True
    ORS_SEGMENT_AVOID_MAX_RINGS: int = 88
    ORS_SEGMENT_AVOID_BBOX_PAD_M: float = 800.0
    ORS_SEGMENT_AVOID_STEP_M: float = 18.0
    ORS_SEGMENT_AVOID_RADIUS_UNEVEN_M: float = 12.0
    ORS_SEGMENT_AVOID_RADIUS_BAD_M: float = 17.0
    ORS_AVOID_MIN_CENTER_SEPARATION_M: float = 6.5

    # Accessibility scoring (obstacles)
    # Temporary obstacles expire after this many hours (when is_temporary=True).
    TEMP_OBSTACLE_TTL_HOURS: int = 72
    # Minimum number of independent verifications required for a report to affect route scoring.
    OBSTACLE_VERIFICATION_THRESHOLD: int = 2
    # Proximity radius used for route-vs-obstacle matching.
    OBSTACLE_ROUTE_BUFFER_METERS: float = 50.0
    # Candidate scoring: penalize each route leg that passes close to a verified hazard.
    # (Flat per-obstacle scoring made all candidates tie when they shared the same reports.)
    ROUTE_SCORE_OBSTACLE_NEAR_LEG_M: float = 22.0
    ROUTE_SCORE_SMOOTH_PAVEMENT_AMPLIFY: float = 1.5

    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB

    # Global ML switch. Set false on tiny hosts for non-ML demos.
    ML_ENABLED: bool = True

    # MobileNetV3 path classification (PyTorch)
    ML_DEVICE: str = "cpu"
    # On small hosts (e.g. Render starter), set false to defer torch model load until first ML request.
    ML_WARMUP_ON_STARTUP: bool = True
    ML_CHECKPOINT_PATH: Optional[str] = None

    # MobileNetV3 obstacle-type classification (PyTorch)
    OBSTACLE_ML_CHECKPOINT_PATH: Optional[str] = None

    # Binary verifiers (MobileNetV3, 2-class logits)
    OBSTRUCTION_VERIFIER_ML_CHECKPOINT_PATH: Optional[str] = None
    SURFACE_PROBLEM_VERIFIER_ML_CHECKPOINT_PATH: Optional[str] = None
    OBSTRUCTION_GATE_THRESHOLD: float = 0.5
    
    # Application
    DEBUG: bool = True
    # Optional public origin for planning CSV/GeoJSON (e.g. https://your-host:8000) so
    # evidence image_url values are absolute links for GIS or work-order systems.
    PUBLIC_API_BASE_URL: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
