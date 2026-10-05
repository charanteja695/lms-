from fastapi import APIRouter

from app.api.v1.endpoints import attempts, grading, internal, my_tests, questions, tests

api_router = APIRouter()
api_router.include_router(questions.router)
api_router.include_router(tests.router)
api_router.include_router(my_tests.router)
api_router.include_router(attempts.router)
api_router.include_router(grading.router)
api_router.include_router(internal.router)
