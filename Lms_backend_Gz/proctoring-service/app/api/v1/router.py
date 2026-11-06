from fastapi import APIRouter

from app.api.v1.endpoints import cases, internal, monitor, sessions

api_router = APIRouter()
api_router.include_router(sessions.router)
api_router.include_router(monitor.router)
api_router.include_router(cases.router)
api_router.include_router(internal.router)
