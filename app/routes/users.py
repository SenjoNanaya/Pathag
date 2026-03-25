from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserResponse, UserUpdate
from app.utils.util_auth import get_current_user

router = APIRouter()