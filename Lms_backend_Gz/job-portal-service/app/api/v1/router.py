from fastapi import APIRouter

from app.api.v1.endpoints import applications, catalog, directory, employers, hiring, institution, jobs

api_router = APIRouter()
api_router.include_router(employers.router)
api_router.include_router(employers.admin)
api_router.include_router(jobs.router)
api_router.include_router(jobs.admin)
api_router.include_router(catalog.router)
api_router.include_router(applications.router)
api_router.include_router(hiring.router)
api_router.include_router(institution.router)
api_router.include_router(institution.drives)
api_router.include_router(directory.router)
