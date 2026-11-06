from fastapi import APIRouter

from app.api.v1.endpoints import (
    academics,
    admins,
    audit_logs,
    auth,
    directory,
    employers,
    hierarchy,
    institutions,
    internal,
    jobs,
    permissions,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admins.router)
api_router.include_router(institutions.router)
api_router.include_router(academics.router)
api_router.include_router(hierarchy.router)
api_router.include_router(employers.router)
api_router.include_router(jobs.router)
api_router.include_router(audit_logs.router)
api_router.include_router(directory.router)
api_router.include_router(permissions.router)
api_router.include_router(internal.router)
