from datetime import datetime, timezone
from app.domain.enums import EmploymentType, LocationType, JobStatus
from app.models.job import Job
from app.schemas.job import CandidateJobOut, EmployerJobOut
from app.api.presenters import candidate_job_out, employer_job_out


def test_candidate_job_out_excludes_hiring_process_and_pipeline():
    # 1. Verify schema model fields
    candidate_forbidden = {"hiring_process", "pipeline", "steps"}
    for field in candidate_forbidden:
        assert field not in CandidateJobOut.model_fields, f"{field} should NOT be in CandidateJobOut.model_fields"

    employer_required = {"hiring_process", "pipeline", "steps"}
    for field in employer_required:
        assert field in EmployerJobOut.model_fields, f"{field} MUST be in EmployerJobOut.model_fields"


def test_candidate_job_out_serialization_excludes_pipeline():
    # Mock a job with hiring_process and pipeline configured
    dummy_job = Job(
        id=101,
        public_id=1755000000000101,
        employer_org_id=2001,
        title="Full Stack Software Engineer",
        description="Build scalable web apps.",
        about_job="Build scalable web apps with Python and React.",
        job_code="JOB-101",
        employment_type=EmploymentType.FULL_TIME.value,
        location_type=LocationType.ONSITE.value,
        locations=["Hyderabad"],
        experience_min_months=12,
        experience_max_months=36,
        ctc_min=600000,
        ctc_max=1200000,
        currency="INR",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        openings=2,
        visibility="public",
        status=JobStatus.OPEN.value,
        created_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
        minimum_qualifications=["B.Tech in CS", "1+ year experience"],
        preferred_qualifications=["AWS certified"],
        responsibilities=["Write code", "Review PRs", "Design APIs"],
        perks=["Health insurance", "Free meals"],
        hiring_process=[
            {"id": "stg_1", "name": "Application Screening"},
            {"id": "stg_2", "name": "Online Assessment"},
            {"id": "stg_3", "name": "Technical Interview"},
            {"id": "stg_4", "name": "HR & Cultural Alignment"},
        ],
        pipeline={"assessment": {"test_id": 555}, "hr_interview": True},
    )

    candidate_dto = candidate_job_out(dummy_job, "Acme Tech", eligible=True, reasons=[])
    data = candidate_dto.model_dump()

    # Assert student view has NO pipeline or hiring stages
    assert "hiring_process" not in data, "hiring_process found in candidate output"
    assert "pipeline" not in data, "pipeline found in candidate output"
    assert "steps" not in data, "steps found in candidate output"

    # Assert student view preserves all public JD details
    assert data["title"] == "Full Stack Software Engineer"
    assert data["about_job"] == "Build scalable web apps with Python and React."
    assert len(data["minimum_qualifications"]) == 2
    assert len(data["responsibilities"]) == 3
    assert len(data["perks"]) == 2

    # Assert employer view retains hiring_process, pipeline, and steps
    employer_dto = employer_job_out(dummy_job, "Acme Tech", institution_ids=[10])
    emp_data = employer_dto.model_dump()
    assert "hiring_process" in emp_data
    assert len(emp_data["hiring_process"]) == 4
    assert "pipeline" in emp_data
    assert "steps" in emp_data
    assert len(emp_data["steps"]) == 4
    assert emp_data["steps"][0]["label"] == "Application Screening"
    print("ALL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_candidate_job_out_excludes_hiring_process_and_pipeline()
    test_candidate_job_out_serialization_excludes_pipeline()
