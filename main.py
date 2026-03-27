from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import routes as routing_routes
from app.routes import auth as auth_routes
from app.routes import users as users_routes
from app.routes import obstacles as obstacles_routes
from app.routes import lgu_reports as lgu_routes
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Pathag backend")
    if not settings.ML_ENABLED:
        logger.info("ML disabled (ML_ENABLED=false)")
    elif settings.ML_WARMUP_ON_STARTUP:
        from app.services.path_classification import get_path_classifier

        get_path_classifier()
        logger.info("Path classifier initialized")

        from app.services.obstacle_classification import get_obstacle_classifier

        get_obstacle_classifier()
        logger.info("Obstacle classifier initialized")
    else:
        logger.info("ML warmup skipped (ML_WARMUP_ON_STARTUP=false); models load on first ML use")

    yield
    logger.info("Shutting down Pathag backend")


app = FastAPI(
    title="Pathag API",
    description="People-centric navigation for accessible pedestrian routes",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"], summary="Liveness check for load balancers (Render, etc.).")
def health():
    return {"status": "ok"}


@app.get(
    "/api/v1/ml/status",
    tags=["ml"],
    summary="ML feature flag status for demos/operations.",
)
def ml_status():
    if settings.ML_ENABLED:
        return {
            "ml_enabled": True,
            "status": "enabled",
            "message": "ML endpoints are enabled.",
        }
    return {
        "ml_enabled": False,
        "status": "disabled",
        "message": "ML is disabled for this deployment.",
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploads_path = Path(settings.UPLOAD_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

if settings.ML_ENABLED:
    from app.routes import ml_combined

    app.include_router(
        ml_combined.router,
        prefix="/api/v1/ml",
        tags=["ml"],
    )

app.include_router(
    auth_routes.router,
    prefix="/api/v1/auth",
    tags=["auth"],
)

app.include_router(
    users_routes.router,
    prefix="/api/v1/users",
    tags=["users"],
)

app.include_router(
    routing_routes.router,
    prefix="/api/v1/routes",
    tags=["routes"],
)

app.include_router(
    obstacles_routes.router,
    prefix="/api/v1",
    tags=["obstacles"],
)

app.include_router(
    lgu_routes.router,
    prefix="/api/v1",
    tags=["lgu"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)