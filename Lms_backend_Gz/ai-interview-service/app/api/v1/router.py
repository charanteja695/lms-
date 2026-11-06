from fastapi import APIRouter

from app.api.v1.endpoints import calibration, employer, interviews, plans

api_router = APIRouter()
api_router.include_router(plans.router)
api_router.include_router(plans.student)
api_router.include_router(interviews.router)
api_router.include_router(employer.router)
api_router.include_router(employer.appeals_router)
api_router.include_router(calibration.router)
