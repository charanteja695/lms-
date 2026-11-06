"""Turn rows into response objects. Kept out of the endpoint modules so every endpoint shows a job, an employer or an application the
same way, and so the rules for who sees what (a candidate never sees a recruiter's notes; only the employer's team sees the rules) live
in one place."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ApplicationStatus
from app.models.application import Application, ApplicationNote, ApplicationStage
from app.models.employer import EmployerProfile
from app.models.job import Job
from app.models.offer import Offer
from app.models.refs import OrgRef, UserRef
from app.pipeline import progress as pipeline_progress
from app.schemas.application import (
    AssessmentOut,
    CandidateSummary,
    MyApplicationOut,
    OfferOut,
    RecruiterApplicationDetail,
    RecruiterApplicationOut,
    ScreeningOut,
    StageOut,
)
from app.schemas.employer import EmployerOut
from app.schemas.job import CandidateJobOut, EligibilityOut, EmployerJobOut, MatchOut
from app.services.application_service import template_of


async def company_names(db: AsyncSession, org_ids: set[int]) -> dict[int, str]:
    if not org_ids:
        return {}
    rows = await db.execute(select(OrgRef.org_id, OrgRef.name).where(OrgRef.org_id.in_(org_ids)))
    return {org_id: name or "Company" for org_id, name in rows.all()}


def employer_out(profile: EmployerProfile, company_name: str, *, open_jobs: int = 0, include_review: bool = True) -> EmployerOut:
    return EmployerOut(
        organization_id=profile.organization_id, company_name=company_name, about=profile.about, website=profile.website, industry=profile.industry,
        company_size=profile.company_size, headquarters=profile.headquarters, status=profile.status, review_note=profile.review_note if include_review else None,
        submitted_at=profile.submitted_at, reviewed_at=profile.reviewed_at, open_jobs=open_jobs,
    )


def _base(job: Job, company_name: str | None, company_website: str | None = None, company_about: str | None = None) -> dict[str, Any]:
    return {
        "job_id": job.public_id, "employer_id": job.employer_org_id, "company_name": company_name,
        "company_website": company_website, "company_about": company_about,
        "job_code": job.job_code or f"JOB-{str(job.public_id)[-6:]}",
        "title": job.title, "description": job.description,
        "employment_type": job.employment_type, "location_type": job.location_type, "locations": list(job.locations or []),
        "experience_min_months": job.experience_min_months, "experience_max_months": job.experience_max_months, "ctc_min": job.ctc_min, "ctc_max": job.ctc_max,
        "stipend_per_month": job.stipend_per_month, "duration_months": job.duration_months,
        "currency": job.currency, "required_skills": list(job.required_skills or []), "preferred_skills": list(job.preferred_skills or []), "openings": job.openings,
        "deadline_at": job.deadline_at, "visibility": job.visibility, "drive_id": job.drive_id, "status": job.status, "published_at": job.published_at, "created_at": job.created_at,
        "banner_text": job.banner_text,
        "banner_type": job.banner_type or "info",
        "experience_level": job.experience_level,
        "experience_level_description": job.experience_level_description,
        "remote_eligible": bool(getattr(job, "remote_eligible", False)),
        "about_job": job.about_job or job.description,
        "responsibilities": list(job.responsibilities or []),
        "minimum_qualifications": list(job.minimum_qualifications or []),
        "preferred_qualifications": list(job.preferred_qualifications or []),
        "perks": list(job.perks or []),
    }


def _job_steps(job: Job) -> list[dict[str, str]]:
    if job.hiring_process and isinstance(job.hiring_process, list) and len(job.hiring_process) > 0:
        return [{"key": str(s.get("id") or idx), "label": str(s.get("name") or f"Stage {idx+1}")} for idx, s in enumerate(job.hiring_process)]
    return pipeline_progress.steps(template_of(job))


def employer_job_out(job: Job, company_name: str | None, *, institution_ids: list[int], applications: int = 0, placed: int = 0, company_website: str | None = None, company_about: str | None = None) -> EmployerJobOut:
    return EmployerJobOut(
        **_base(job, company_name, company_website, company_about),
        job_details=dict(job.job_details or {}),
        hiring_process=list(job.hiring_process or []),
        application_config=dict(job.application_config or {}),
        eligibility={**(job.eligibility or {}), "institution_ids": [str(i) for i in institution_ids]},
        institution_ids=[str(i) for i in institution_ids],
        pipeline=dict(job.pipeline or {}),
        steps=_job_steps(job),
        review_note=job.review_note,
        closed_reason=job.closed_reason,
        applications=applications,
        placed=placed,
        created_by=job.created_by,
    )


def candidate_job_out(
    job: Job, company_name: str | None, *, eligible: bool | None = None, reasons: list[str] | None = None, match: tuple[int, list[str], dict[str, float], str] | None = None,
    application_id: int | None = None, company_website: str | None = None, company_about: str | None = None,
) -> CandidateJobOut:
    return CandidateJobOut(
        **_base(job, company_name, company_website, company_about),
        eligibility_result=EligibilityOut(eligible=eligible, reasons=reasons or []) if eligible is not None else None,
        match=MatchOut(score=match[0], explanation=match[1], breakdown=match[2], method=match[3]) if match else None,
        applied=application_id is not None,
        application_id=application_id,
    )


# ---------------------------------------------------------------- applications
def stage_out(stage: ApplicationStage) -> StageOut:
    return StageOut(from_status=stage.from_status, to_status=stage.to_status, actor=stage.actor, note=stage.note, created_at=stage.created_at)


def offer_out(offer: Offer | None) -> OfferOut | None:
    return OfferOut.model_validate(offer) if offer is not None else None


def _assessment(application: Application) -> AssessmentOut | None:
    if application.assessment_test_id is None:
        return None
    return AssessmentOut(
        test_id=application.assessment_test_id, invite_state=application.assessment_invite_state, percent=application.assessment_percent,
        result=application.assessment_result, integrity=application.assessment_integrity,
    )


def my_application_out(
    application: Application, job: Job, company_name: str | None, *, history: list[ApplicationStage] | None = None, offer: Offer | None = None,
    stopped_from: str | None = None,
) -> MyApplicationOut:
    """What the candidate sees: their status, progress through the job's steps, what to do next and the history — never the recruiter's
    notes or the screening. ``stopped_from``: for a closed application, the status it was in when it closed (else read from ``history``)."""
    status = ApplicationStatus(application.status)
    if stopped_from is None and history:
        stopped_from = history[-1].from_status
    steps = pipeline_progress.progress(status, template_of(job), stopped_from=ApplicationStatus(stopped_from) if stopped_from else None)
    # Hide future roadmap stages from the student's progress view
    visible_steps = [s for s in steps if s.get("state") != "upcoming"]
    action = pipeline_progress.next_action(
        status, assessment_invite_state=application.assessment_invite_state, offer_status=offer.status if offer else None, offer_expires_at=offer.expires_at if offer else None
    )
    return MyApplicationOut(
        application_id=application.public_id, job_id=job.public_id, job_title=job.title, company_name=company_name, status=application.status,
        match_score=application.match_score, match_explanation=application.match_explanation, resume_version_no=application.resume_version_no, assessment=_assessment(application),
        offer=offer_out(offer), history=[stage_out(s) for s in history or []], progress=visible_steps, next_action=action.as_dict() if action else None,
        applied_at=application.created_at, status_changed_at=application.status_changed_at,
    )


def _name(user: UserRef | None, resume: dict[str, Any] | None = None) -> str:
    name = " ".join(x for x in ((user.first_name if user else ""), (user.last_name if user else "")) if x)
    if not name and resume:
        name = (resume.get("personal") or {}).get("name") or ""
    return name or "Candidate"


def recruiter_application_out(
    application: Application,
    user: UserRef | None,
    job_public_id: int,
    *,
    job_title: str | None = None,
    company_name: str | None = None,
    institution_name: str | None = None,
    profile_facts: dict[str, Any] | None = None,
) -> RecruiterApplicationOut:
    interview = None
    if application.interview_recommendation or application.interview_score is not None:
        interview = {"recommendation": application.interview_recommendation, "score": application.interview_score, "report": application.interview_report}

    resume = application.resume_snapshot or {}
    personal = resume.get("personal") or {}
    education = resume.get("education") or []
    first_edu = education[0] if education else {}
    facts = profile_facts or {}

    name = _name(user, resume)
    email = (user.email if user else None) or personal.get("email")
    phone = personal.get("phone")
    branch = facts.get("branch") or first_edu.get("field")
    cgpa = facts.get("cgpa")
    if cgpa is None and first_edu.get("cgpa") is not None:
        try:
            cgpa = float(first_edu.get("cgpa"))
        except (ValueError, TypeError):
            pass
    grad_year = facts.get("graduation_year")
    if grad_year is None and first_edu.get("end_year") is not None:
        try:
            grad_year = int(first_edu.get("end_year"))
        except (ValueError, TypeError):
            pass
    roll_number = facts.get("roll_number") or facts.get("admission_number") or str(application.user_id)
    inst_name = institution_name or first_edu.get("institution")

    candidate = CandidateSummary(
        user_id=application.user_id,
        name=name,
        email=email,
        phone=phone,
        roll_number=roll_number,
        institution_name=inst_name,
        branch=branch,
        graduation_year=grad_year,
        cgpa=cgpa,
    )

    return RecruiterApplicationOut(
        application_id=application.public_id,
        job_id=job_public_id,
        job_title=job_title,
        company_name=company_name,
        candidate=candidate,
        status=application.status,
        match_score=application.match_score,
        match_explanation=application.match_explanation,
        screening=ScreeningOut(
            score=application.screen_score,
            recommendation=application.screen_recommendation,
            source=application.screen_source,
            reasons=list(application.screen_reasons or []),
            red_flags=list(application.screen_red_flags or []),
        ),
        assessment=_assessment(application),
        interview=interview,
        hr_interview_at=application.hr_interview_at,
        cover_note=application.cover_note,
        resume_version_no=application.resume_version_no,
        applied_at=application.created_at,
        status_changed_at=application.status_changed_at,
        decision_reason=application.decision_reason,
    )


def recruiter_application_detail(
    application: Application,
    user: UserRef | None,
    job: Job,
    *,
    history: list[ApplicationStage],
    notes: list[ApplicationNote],
    offer: Offer | None,
    company_name: str | None = None,
    institution_name: str | None = None,
    profile_facts: dict[str, Any] | None = None,
) -> RecruiterApplicationDetail:
    base = recruiter_application_out(
        application,
        user,
        job.public_id,
        job_title=job.title,
        company_name=company_name,
        institution_name=institution_name,
        profile_facts=profile_facts,
    )
    app_config = job.application_config or {}
    return RecruiterApplicationDetail(
        **{name: getattr(base, name) for name in RecruiterApplicationOut.model_fields},
        resume=application.resume_snapshot or {},
        history=[stage_out(s) for s in history],
        notes=[{"author_user_id": str(n.author_user_id), "body": n.body, "created_at": n.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")} for n in notes],
        offer=offer_out(offer),
        answers=dict(application.answers or {}),
        questions=list(app_config.get("questions") or []),
    )
