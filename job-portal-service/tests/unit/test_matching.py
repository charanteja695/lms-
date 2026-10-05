from dataclasses import replace

import pytest

from app.matching import eligibility
from app.matching.model import Candidate, JobSpec, Preferences
from app.matching.scoring import Weights, score, verified_terms
from app.matching.text import canonical, dense_cosine, lexical_cosine, scale_dense, scale_lexical, tokens

COURSES = {1: "Python Programming", 2: "SQL for Data", 3: "Web Design"}
JOB = JobSpec(
    title="Backend Developer", description="Build REST APIs with Python and FastAPI on PostgreSQL. Docker and AWS are a plus.",
    required_skills=("Python", "FastAPI", "PostgreSQL", "Docker"), preferred_skills=("AWS", "Redis"), locations=("Chennai", "Bengaluru"), location_type="onsite", employment_type="full_time",
    experience_min_months=12, ctc_max=1_200_000,
)
ASHA = Candidate(user_id=1, organization_id=10, skills=("Python", "SQL"), technologies=("FastAPI", "postgres"), job_titles=("Software Intern",), experience_months=3, graduation_year=2026,
                 certificate_course_ids=frozenset({1}), scores={1: 91.5}, education=("B.Tech Computer Science",), location="Chennai, India", target_roles=("Backend Developer",))


def rate(candidate=ASHA, job=JOB, prefs=Preferences(), semantic=0.5, **kw):  # noqa: B008
    return score(job, candidate, prefs, courses=COURSES, semantic=semantic, semantic_method="lexical", **kw)


# ---------------------------------------------------------------- words
def test_canonical_folds_spellings_plurals_and_aliases():
    assert canonical("Node.js") == canonical("NodeJS") == "node"
    assert canonical("K8s") == canonical("Kubernetes") == "kubernetes" and canonical("Postgres") == canonical("PostgreSQL") == "postgresql"
    assert canonical("APIs") == "api" and canonical("Libraries") == "library" and canonical("AWS") == canonical("Amazon Web Services") == "aws" and canonical("Class") == "class"


def test_similarity_helpers():
    assert lexical_cosine("python backend api", "python backend api") == pytest.approx(1.0)
    assert lexical_cosine("python backend", "gardening tulips") == 0.0 and lexical_cosine("", "x") == 0.0
    assert 0.3 < lexical_cosine(ASHA.text, JOB.text) < 0.7
    assert dense_cosine([1, 0], [1, 0]) == pytest.approx(1.0) and dense_cosine([1, 0], [0, 1]) == 0.0 and dense_cosine([1], [1, 2]) == 0.0
    assert scale_lexical(0.4) == 1.0 and scale_lexical(0.2) == pytest.approx(0.5) and scale_dense(0.25) == 0.0 and scale_dense(0.75) == 1.0 and scale_dense(0.9) == 1.0
    assert "the" not in tokens("the Python and the SQL")


# ---------------------------------------------------------------- eligibility
def spec(**rules):
    restricted = rules.pop("restricted", False)
    institutions = frozenset(rules.pop("institutions", ()))
    return JobSpec(title="T", description="d", required_skills=("x",), eligibility=rules, restricted=restricted, institution_ids=institutions)


def test_no_rules_means_everyone_is_eligible():
    assert eligibility.check(spec(), ASHA, course_titles=COURSES).eligible


def test_graduation_year_rule():
    ok = eligibility.check(spec(graduation_years={"min": 2025, "max": 2026}), ASHA, course_titles=COURSES)
    assert ok.eligible
    late = eligibility.check(spec(graduation_years={"min": 2027, "max": 2028}), ASHA, course_titles=COURSES)
    assert not late.eligible and late.reasons == ["Open to graduation years 2027–2028 (yours: 2026)."]
    assert eligibility.check(spec(graduation_years={"min": 2027, "max": None}), ASHA, course_titles=COURSES).reasons == ["Open to graduation years 2027 or later (yours: 2026)."]
    unknown = eligibility.check(spec(graduation_years={"min": 2025, "max": 2026}), Candidate(user_id=2, organization_id=None), course_titles=COURSES)
    assert not unknown.eligible and "Add your education" in unknown.reasons[0]


def test_certificate_and_score_rules_say_what_is_missing():
    result = eligibility.check(spec(certificate_course_ids=["1", "2"], min_scores=[{"course_id": "1", "min_percent": 95}, {"course_id": "2", "min_percent": 60}]), ASHA, course_titles=COURSES)
    assert result.reasons == ["Requires the certificate for SQL for Data.", "Requires at least 95% in Python Programming (yours: 91.5%).", "Requires at least 60% in SQL for Data (you have no passed result yet)."]
    assert eligibility.check(spec(certificate_course_ids=["1"], min_scores=[{"course_id": "1", "min_percent": 90}]), ASHA, course_titles=COURSES).eligible


def test_restricted_jobs_need_the_right_institution():
    assert eligibility.check(spec(restricted=True, institutions=[10, 11]), ASHA, course_titles=COURSES).eligible
    other = eligibility.check(spec(restricted=True, institutions=[11]), ASHA, course_titles=COURSES)
    assert other.reasons == ["This job is open only to students of selected institutions."]
    assert not eligibility.check(spec(restricted=True, institutions=[10]), Candidate(user_id=3, organization_id=None), course_titles=COURSES).eligible
    assert eligibility.check(spec(restricted=False), Candidate(user_id=3, organization_id=None), course_titles=COURSES).eligible


# ---------------------------------------------------------------- score
def test_verified_terms_credit_grows_with_the_score():
    terms = verified_terms(COURSES, frozenset({1, 2}), {1: 100.0})
    assert terms["python"] == pytest.approx(1.0) and terms["sql"] == pytest.approx(0.85)  # a certificate alone earns the base credit
    assert verified_terms(COURSES, frozenset(), {}) == {} and verified_terms({}, frozenset({1}), {1: 90}) == {}


def test_the_score_explains_itself():
    result = rate()
    assert 0 <= result.score <= 100 and sum(result.breakdown.values()) == pytest.approx(result.score, abs=1)
    assert result.explanation[0] == "Matches 3/4 required skills; missing: Docker"
    assert "Preferred skills: 0/2" in result.explanation and any(line.startswith("Verified on the platform: Python") for line in result.explanation)
    assert any(line.startswith("Relevant certificate: Python Programming") for line in result.explanation)
    assert "Location matches (Chennai)" in result.explanation and "Matches a role you are looking for" in result.explanation
    assert any("Asks for 1 year of experience; you have 3 months" == line for line in result.explanation)
    assert result.semantic_method == "lexical" and result.semantic_similarity == 0.5


def test_weights_are_respected_and_bound_the_score():
    perfect = Candidate(user_id=9, organization_id=1, skills=("Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Redis"), certificate_course_ids=frozenset({1}), scores={1: 100.0}, target_roles=("Backend Developer",), location="Chennai")
    top = rate(perfect, semantic=1.0, prefs=Preferences(locations=("Chennai",), roles=("Backend Developer",), min_ctc=900_000, employment_types=("full_time",)))
    assert top.score >= 80 and top.breakdown["skills"] < 50  # skills only declared, not verified, cannot earn every point: verification is what lifts a score to the top
    nothing = rate(Candidate(user_id=8, organization_id=1), semantic=0.0)
    assert nothing.score < 20 and nothing.breakdown["skills"] == 0
    only_skills = rate(perfect, semantic=1.0, weights=Weights(skills=100, semantic=0, certificates=0, preferences=0))
    assert only_skills.breakdown["semantic"] == 0 and only_skills.score == only_skills.breakdown["skills"] == 76  # the weights, not fixed numbers, decide the scale


def test_a_verified_skill_outweighs_a_declared_one_and_a_higher_score_beats_a_lower_one():
    declared = Candidate(user_id=1, organization_id=1, skills=("Python",))
    low = Candidate(user_id=2, organization_id=1, skills=("Python",), certificate_course_ids=frozenset({1}), scores={1: 60.0})
    high = Candidate(user_id=3, organization_id=1, skills=("Python",), certificate_course_ids=frozenset({1}), scores={1: 100.0})
    only_python = JobSpec(title="Dev", description="", required_skills=("Python",))
    a, b, c = (rate(x, only_python, semantic=0.0).breakdown["skills"] for x in (declared, low, high))
    assert a < b < c and a == pytest.approx(35.0) and c == pytest.approx(50.0)


def test_a_course_the_student_finished_counts_even_if_the_skill_was_never_listed():
    skillless = Candidate(user_id=4, organization_id=1, certificate_course_ids=frozenset({2}), scores={2: 88.0})
    sql_job = JobSpec(title="Analyst", description="", required_skills=("SQL",))
    assert rate(skillless, sql_job, semantic=0.0).breakdown["skills"] > 40


def test_unset_preferences_are_neutral_and_set_ones_bite():
    neutral = rate(Candidate(user_id=5, organization_id=1, skills=("Python",)), semantic=0.0)
    assert neutral.breakdown["preferences"] == pytest.approx(10.0)  # half of 20
    wants_far = rate(replace(ASHA, target_roles=()), semantic=0.0, prefs=Preferences(locations=("Delhi",), open_to_remote=False, roles=("Data Scientist",), min_ctc=5_000_000, employment_types=("internship",)))
    assert wants_far.breakdown["preferences"] == 0.0
    assert {"Location differs from your preference", "Pay is below your minimum", "Not a kind of job you asked for"} <= set(wants_far.explanation)
    remote = JobSpec(title="Backend Developer", description="", required_skills=("Python",), location_type="remote")
    assert "Remote-friendly" in rate(ASHA, remote, prefs=Preferences(locations=("Delhi",))).explanation
    assert "Remote-friendly" not in rate(ASHA, remote, prefs=Preferences(locations=("Delhi",), open_to_remote=False)).explanation


def test_no_personal_attribute_can_change_a_score():
    """The scorer's inputs do not contain a name, email, gender or photo; two candidates who differ only in id and institution score alike."""
    twin = Candidate(
        user_id=2, organization_id=99, skills=ASHA.skills, technologies=ASHA.technologies, job_titles=ASHA.job_titles, experience_months=ASHA.experience_months, graduation_year=ASHA.graduation_year,
        certificate_course_ids=ASHA.certificate_course_ids, scores=ASHA.scores, education=ASHA.education, location=ASHA.location, target_roles=ASHA.target_roles,
    )
    assert rate(ASHA).score == rate(twin).score
    assert {f for f in Candidate.__slots__} == {"user_id", "organization_id", "skills", "technologies", "job_titles", "experience_months", "graduation_year", "certificate_course_ids", "scores", "education", "location", "target_roles", "headline"}
