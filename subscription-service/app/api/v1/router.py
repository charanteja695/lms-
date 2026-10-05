from fastapi import APIRouter

from app.api.v1.endpoints import course_requests, seats, subscriptions

api_router = APIRouter()
api_router.include_router(course_requests.router)
api_router.include_router(subscriptions.router)
api_router.include_router(seats.router)
