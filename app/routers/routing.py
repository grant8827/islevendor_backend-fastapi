from math import atan2, cos, radians, sin, sqrt

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/routing", tags=["routing"])

EARTH_RADIUS_METERS = 6_371_000


class Coordinate(BaseModel):
    lat: float
    lng: float


class DistanceMatrixRequest(BaseModel):
    origin: Coordinate
    destinations: list[Coordinate]


class DistanceResult(BaseModel):
    destination: Coordinate
    distance_meters: float


class DistanceMatrixResponse(BaseModel):
    method: str
    results: list[DistanceResult]


def haversine_meters(a: Coordinate, b: Coordinate) -> float:
    lat1, lat2 = radians(a.lat), radians(b.lat)
    dlat = radians(b.lat - a.lat)
    dlng = radians(b.lng - a.lng)
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * atan2(sqrt(h), sqrt(1 - h))


@router.post("/distance-matrix", response_model=DistanceMatrixResponse)
async def distance_matrix(payload: DistanceMatrixRequest) -> DistanceMatrixResponse:
    """Straight-line (haversine) distance from origin to each destination.

    This is real math, not a stub — but it's straight-line, not road-network,
    distance. It's fine as an initial driver-proximity ranking signal (which is
    all Domain D's dispatch needs today), but understates real drive distance/
    time on Jamaica's road network. Swap in OSRM or Google's Distance Matrix
    API here before using this for ETA promises to customers.
    """
    results = [
        DistanceResult(destination=dest, distance_meters=haversine_meters(payload.origin, dest))
        for dest in payload.destinations
    ]
    return DistanceMatrixResponse(method="haversine_straight_line", results=results)
