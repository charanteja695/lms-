from fastapi import APIRouter

from app.api.v1.endpoints import deliveries, notifications, preferences, templates

api_router = APIRouter()
api_router.include_router(notifications.router)
api_router.include_router(preferences.router)
api_router.include_router(templates.router)
api_router.include_router(deliveries.router)
