from fastapi import APIRouter

from app.api.v1.endpoints import courses, learning_paths, modules, topic_items, topics, versions

api_router = APIRouter()
api_router.include_router(courses.router)
api_router.include_router(versions.router)
api_router.include_router(modules.router)
api_router.include_router(topics.router)
api_router.include_router(topic_items.router)
api_router.include_router(learning_paths.router)
