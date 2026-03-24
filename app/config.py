from pydantic_settings import BaseSettings
from typing import Optional


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
    
    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB

    # MobileNetV3 path classification (PyTorch)
    ML_DEVICE: str = "cpu"
    ML_CHECKPOINT_PATH: Optional[str] = None
    
    # Application
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()
