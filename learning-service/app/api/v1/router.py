from fastapi import APIRouter

from app.api.v1.endpoints import batches, enrollments, progress

api_router = APIRouter()
api_router.include_router(batches.router)
api_router.include_router(enrollments.router)
api_router.include_router(progress.router)
