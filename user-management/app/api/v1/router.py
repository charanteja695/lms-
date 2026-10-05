from fastapi import APIRouter

from app.api.v1.endpoints import admins, audit_logs, auth, employers, institutions, jobs, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admins.router)
api_router.include_router(institutions.router)
api_router.include_router(employers.router)
api_router.include_router(jobs.router)
api_router.include_router(audit_logs.router)
