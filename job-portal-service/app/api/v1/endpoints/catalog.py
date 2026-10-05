"""What a student sees: browse and search jobs, one job with their eligibility and match, recommendations, preferences."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from lms_common.pagination import LIKE_ESCAPE, contains_pattern
from sqlalchemy import String, and_, cast, func, or_, select

from app.api.deps import DbSession, JobIdParam, RequireStudent, SettingsDep, WriteRateLimit
from app.api.presenters import candidate_job_out, company_names
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError
from app.domain.enums import EmploymentType, LocationType
from app.matching import eligibility
from app.models.application import Application
from app.models.job import Job
from app.models.match import JobMatch
from app.schemas.application import PreferencesIn, PreferencesOut, PreferencesResponse
from app.schemas.job import CandidateJobOut, CandidateJobPage, CandidateJobResponse
from app.services.candidate_service import CandidateService, to_candidate, to_preferences
from app.services.job_service import JobService
from app.services.match_service import MatchService

router = APIRouter(tags=["Jobs (student)"])


def _like(value: str) -> str:
    return contains_pattern(value.strip().lower())


async def _present(
    db: DbSession, settings: SettingsDep, auth: RequireStudent, jobs: list[Job], matches: dict[object, JobMatch] | None = None
) -> list[CandidateJobOut]:
    """Add what only this student can see to each job: whether they may apply and why not, their match, whether they have applied."""
    if not jobs:
        return []
    candidates = CandidateService(db)
    profile = await candidates.profile(auth.user_id)
    candidate = to_candidate(profile) if profile else None
    courses = await candidates.course_titles(None) if candidate else {}
    names = await company_names(db, {j.employer_org_id for j in jobs})
    job_service = JobService(db, settings)
    if matches is None:
        rows = await db.execute(select(JobMatch).where(JobMatch.user_id == auth.user_id, JobMatch.job_id.in_([j.id for j in jobs])))
        matches = {m.job_id: m for m in rows.scalars()}
    applied = {
        job_id: public_id
        for job_id, public_id in (await db.execute(select(Application.job_id, Application.public_id).where(Application.user_id == auth.user_id, Application.job_id.in_([j.id for j in jobs])))).all()
    }
    out: list[CandidateJobOut] = []
    for job in jobs:
        eligible: bool | None = None
        reasons: list[str] = []
        if candidate is not None:
            verdict = eligibility.check(await job_service.spec(job), candidate, course_titles=courses)
            eligible, reasons = verdict.eligible, verdict.reasons
        else:
            eligible, reasons = False, ["Build your skill profile (it needs a certificate or a passed assessment) to see if you are eligible."]
        match = matches.get(job.id)
        out.append(
            candidate_job_out(
                job, names.get(job.employer_org_id), eligible=eligible, reasons=reasons,
                match=(match.score, list(match.explanation), dict(match.breakdown), match.semantic_method) if match else None, application_id=applied.get(job.id),
            )
        )
    return out


@router.get(
    "/job-board", response_model=CandidateJobPage, summary="Browse and search open jobs",
    description="Open jobs from verified companies that this student may see: public jobs, and jobs restricted to their institution (placement drives). Each carries the student's "
    "`eligibility_result` (with the reasons if they are not eligible) and their `match` when they have one. `sort=relevance` puts the best matches first.",
    responses=errors(*AUTHENTICATED),
)
async def browse(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, q: Annotated[str | None, Query(max_length=100)] = None, location: Annotated[str | None, Query(max_length=80)] = None,
    employment_type: Annotated[EmploymentType | None, Query()] = None, location_type: Annotated[LocationType | None, Query()] = None, skill: Annotated[str | None, Query(max_length=60)] = None,
    min_ctc: Annotated[int | None, Query(ge=0)] = None, eligible_only: Annotated[bool, Query()] = False,
    sort: Annotated[str, Query(pattern="^(relevance|newest|deadline|pay)$")] = "relevance", page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CandidateJobPage:
    stmt = select(Job).outerjoin(JobMatch, and_(JobMatch.job_id == Job.id, JobMatch.user_id == auth.user_id)).where(JobService.visible_to_students(auth.organization_id))
    if q:
        term = _like(q)
        stmt = stmt.where(or_(func.lower(Job.title).like(term, escape=LIKE_ESCAPE), func.lower(Job.description).like(term, escape=LIKE_ESCAPE)))
    if location:
        stmt = stmt.where(func.lower(cast(Job.locations, String)).like(_like(location), escape=LIKE_ESCAPE))
    if employment_type:
        stmt = stmt.where(Job.employment_type == employment_type.value)
    if location_type:
        stmt = stmt.where(Job.location_type == location_type.value)
    if skill:
        quoted = contains_pattern(f'"{skill.strip().lower()}"')
        stmt = stmt.where(or_(func.lower(cast(Job.required_skills, String)).like(quoted, escape=LIKE_ESCAPE), func.lower(cast(Job.preferred_skills, String)).like(quoted, escape=LIKE_ESCAPE)))
    if min_ctc is not None:
        stmt = stmt.where(Job.ctc_max >= min_ctc)
    order = {
        "relevance": (JobMatch.score.desc().nullslast(), Job.published_at.desc().nullslast()), "newest": (Job.published_at.desc().nullslast(),),
        "deadline": (Job.deadline_at.asc().nullslast(),), "pay": (Job.ctc_max.desc().nullslast(),),
    }[sort]
    if not eligible_only:
        total = int((await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        jobs = list((await db.execute(stmt.order_by(*order, Job.id).limit(per_page).offset((page - 1) * per_page))).scalars())
        presented = await _present(db, settings, auth, jobs)
    else:
        # eligibility is worked out per student in code, so filter a bounded window of the best-ranked jobs and page over that
        window = list((await db.execute(stmt.order_by(*order, Job.id).limit(500))).scalars())
        presented_all = [j for j in await _present(db, settings, auth, window) if j.eligibility_result and j.eligibility_result.eligible]
        total = len(presented_all)
        presented = presented_all[(page - 1) * per_page : page * per_page]
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column=sort, sort_order=SortOrder.DESC)
    return CandidateJobPage(message="", jobs=presented, page_context=context)


@router.get("/job-board/{job_id}", response_model=CandidateJobResponse, summary="One job, with my eligibility and my match", responses=errors(*AUTHENTICATED, 404))
async def get_job(job_id: JobIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> CandidateJobResponse:
    job = await JobService(db, settings).get(job_id)
    seen = (await db.execute(select(Job.id).where(Job.id == job.id, JobService.visible_to_students(auth.organization_id)))).first()
    mine = (await db.execute(select(Application.id).where(Application.job_id == job.id, Application.user_id == auth.user_id))).first()
    if seen is None and mine is None:  # a job they applied to stays readable after it closes
        raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
    return CandidateJobResponse(message="", job=(await _present(db, settings, auth, [job]))[0])


@router.get(
    "/recommendations", response_model=CandidateJobPage, summary="Recommended jobs",
    description="The student's best matches among the open jobs they can see, highest first, each with the explanation (\"Matches 6/8 required skills; missing: Docker, AWS\"). "
    "Empty until the student has a verified skill profile, and while `open_to_work` is off.", responses=errors(*AUTHENTICATED),
)
async def recommendations(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, page: Annotated[int, Query(ge=1, le=1_000)] = 1,
    per_page: Annotated[int | None, Query(ge=1, le=50)] = None,
) -> CandidateJobPage:
    limit = per_page or settings.RECOMMENDATIONS_DEFAULT_LIMIT
    preferences = to_preferences(await CandidateService(db).preferences(auth.user_id))
    pairs = await MatchService(db, settings).matches_for(auth.user_id, auth.organization_id, limit=limit, offset=(page - 1) * limit) if preferences.open_to_work else []
    out = await _present(db, settings, auth, [job for job, _ in pairs], matches={job.id: match for job, match in pairs})
    total = int((await db.execute(select(func.count()).select_from(select(JobMatch.id).join(Job, Job.id == JobMatch.job_id).where(JobMatch.user_id == auth.user_id, JobService.visible_to_students(auth.organization_id)).subquery()))).scalar_one()) if preferences.open_to_work else 0
    context = PageContext.build(page=page, per_page=limit, total=total, is_exact=True, sort_column="score", sort_order=SortOrder.DESC)
    return CandidateJobPage(message="", jobs=out, page_context=context)


def _preferences_out(row: object) -> PreferencesOut:
    prefs = to_preferences(row)  # type: ignore[arg-type]
    return PreferencesOut(
        locations=list(prefs.locations), open_to_remote=prefs.open_to_remote, roles=list(prefs.roles), min_ctc=prefs.min_ctc, employment_types=list(prefs.employment_types), open_to_work=prefs.open_to_work
    )


@router.get("/job-preferences", response_model=PreferencesResponse, summary="My job preferences", responses=errors(*AUTHENTICATED))
async def get_preferences(auth: RequireStudent, db: DbSession) -> PreferencesResponse:
    return PreferencesResponse(message="", preferences=_preferences_out(await CandidateService(db).preferences(auth.user_id)))


@router.put(
    "/job-preferences", response_model=PreferencesResponse, summary="Set my job preferences",
    description="Location, roles, minimum pay, kinds of job, remote. They are 20 of the 100 match points; anything left unset earns half its points. Changing them re-scores your matches.",
    responses=errors(*AUTHENTICATED), dependencies=[WriteRateLimit],
)
async def put_preferences(body: PreferencesIn, auth: RequireStudent, db: DbSession) -> PreferencesResponse:
    row = await CandidateService(db).save_preferences(auth.user_id, body.model_dump(exclude_unset=True, mode="json"))
    return PreferencesResponse(message="Saved.", preferences=_preferences_out(row))
