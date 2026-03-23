from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.models import User, Route
from app.schemas.schemas import RouteRequest, RouteResponse
from app.services.routing import RoutingService
from app.utils.util_auth import get_current_user

router = APIRouter()