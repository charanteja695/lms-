from fastapi import APIRouter

from app.api.v1.endpoints import dashboards, reports

api_router = APIRouter()
api_router.include_router(dashboards.router)
api_router.include_router(reports.router)
