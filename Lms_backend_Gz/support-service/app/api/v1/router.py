from fastapi import APIRouter

from app.api.v1.endpoints import agent, attachments, tickets

api_router = APIRouter()
api_router.include_router(tickets.router)
api_router.include_router(attachments.router)
api_router.include_router(agent.router)
api_router.include_router(agent.admin)
api_router.include_router(agent.internal)
