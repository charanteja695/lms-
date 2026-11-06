from fastapi import APIRouter

from app.api.v1.endpoints import certificates, templates

api_router = APIRouter()
api_router.include_router(templates.router)
api_router.include_router(certificates.router)
