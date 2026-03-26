from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://pathag:pathag@localhost:5432/pathag"
    
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

    # Accessibility scoring (obstacles)
    # Temporary obstacles expire after this many hours (when is_temporary=True).
    TEMP_OBSTACLE_TTL_HOURS: int = 72
    # Minimum number of independent verifications required for a report to affect route scoring.
    OBSTACLE_VERIFICATION_THRESHOLD: int = 2
    # Proximity radius used for route-vs-obstacle matching.
    OBSTACLE_ROUTE_BUFFER_METERS: float = 50.0
    
    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB

    # MobileNetV3 path classification (PyTorch)
    ML_DEVICE: str = "cpu"
    ML_CHECKPOINT_PATH: Optional[str] = None

    # MobileNetV3 obstacle-type classification (PyTorch)
    OBSTACLE_ML_CHECKPOINT_PATH: Optional[str] = None

    # Binary verifiers (MobileNetV3, 2-class logits)
    OBSTRUCTION_VERIFIER_ML_CHECKPOINT_PATH: Optional[str] = None
    SURFACE_PROBLEM_VERIFIER_ML_CHECKPOINT_PATH: Optional[str] = None
    
    # Application
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()
