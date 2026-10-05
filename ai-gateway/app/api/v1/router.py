from fastapi import APIRouter

from app.api.v1.endpoints import internal, logs, models, prompts, quotas

api_router = APIRouter()
api_router.include_router(prompts.router)
api_router.include_router(quotas.router)
api_router.include_router(logs.router)
api_router.include_router(models.router)
api_router.include_router(internal.router)
