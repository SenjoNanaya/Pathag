from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.models import Route
from app.schemas.schemas import RouteRequest, RouteResponse
from app.services.routing import RoutingService

router = APIRouter()


@router.post(
    "/calculate",
    response_model=RouteResponse,
    summary="Calculate accessibility-aware walking route (prototype + ORS option)",
)
async def calculate_route(
    request: RouteRequest,
    db: Session = Depends(get_db),
) -> RouteResponse:
    """
    Calculates a route geometry + steps and scores accessibility using obstacle reports.

    Auth is optional in this repo; if you provide preferences in `RouteRequest`, they
    will still influence scoring.
    """

    routing_service = RoutingService(db=db)
    return await routing_service.calculate_route(request=request, user=None)
