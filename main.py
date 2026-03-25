from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import ml_classification
from app.routes import routes as routing_routes
from app.routes import auth as auth_routes
from app.routes import users as users_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Pathag backend")
    from app.services.path_classification import get_path_classifier

    get_path_classifier()
    logger.info("Path classifier initialized")
    yield
    logger.info("Shutting down Pathag backend")


app = FastAPI(
    title="Pathag API",
    description="People-centric navigation for accessible pedestrian routes",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    ml_classification.router,
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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)