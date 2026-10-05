from fastapi import APIRouter

from app.api.v1.endpoints import conversations, faq, operations

api_router = APIRouter()
api_router.include_router(conversations.router)
api_router.include_router(faq.router)
api_router.include_router(operations.router)
api_router.include_router(operations.internal)
