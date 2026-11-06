from fastapi import APIRouter

from app.api.v1.endpoints import media_assets, playback

api_router = APIRouter()
api_router.include_router(media_assets.router)
api_router.include_router(playback.router)
