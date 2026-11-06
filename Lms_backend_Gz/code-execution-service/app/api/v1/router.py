from fastapi import APIRouter

from app.api.v1.endpoints import internal, languages, problems, review, runs, saved_code, submissions, test_cases

api_router = APIRouter()
api_router.include_router(languages.router)
api_router.include_router(runs.router)
api_router.include_router(problems.router)
api_router.include_router(test_cases.router)
api_router.include_router(saved_code.router)
api_router.include_router(submissions.router)
api_router.include_router(review.router)
api_router.include_router(internal.router)
