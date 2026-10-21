"""A self-registered learner's own course access (bought in the learner store)."""

from fastapi import APIRouter

from app.api.deps import CurrentAuth, DbSession
from app.api.responses import errors
from app.schemas.course_access import CourseAccessListResponse, CourseAccessOut
from app.services.course_access_service import CourseAccessService

router = APIRouter(prefix="/me/course-access", tags=["Learner course access"])


@router.get("", response_model=CourseAccessListResponse, summary="My bought courses and until when I can study them", responses=errors(401))
async def my_course_access(auth: CurrentAuth, db: DbSession) -> CourseAccessListResponse:
    rows = await CourseAccessService(db).mine(auth.user_id)
    return CourseAccessListResponse(message="", course_access=[CourseAccessOut.model_validate(a) for a in rows])
