import math
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Point
from geoalchemy2.elements import WKTElement

from app.models.models import PathSegment, ObstacleReport, User, PathCondition, ObstacleType
from app.schemas.schemas import RouteRequest, RouteResponse, RouteStep, Coordinate