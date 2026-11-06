from fastapi import APIRouter

from app.api.v1.endpoints import internal, profile, resume_ai, resumes

api_router = APIRouter()
api_router.include_router(profile.router)
api_router.include_router(profile.students)
api_router.include_router(resumes.router)
api_router.include_router(resume_ai.router)
api_router.include_router(resume_ai.public)
api_router.include_router(internal.router)
