from app.ai.guard import invented, unsupported_keywords
from app.ats import keywords as kw
from app.ats.language import check_text, is_quantified, starts_with_action_verb


# ---------------------------------------------------------------- the "never invent" guard
def test_a_faithful_rewrite_has_no_findings():
    source = "worked on a REST API in Python that served 2000 requests per minute"
    assert invented(source, "Built a REST API in Python serving 2000 requests per minute.") == []


def test_invented_numbers_are_caught_but_reformatted_ones_are_not():
    source = "Fixed bugs in the checkout flow, 1,200 orders a day"
    assert [f.value for f in invented(source, "Fixed 40 bugs in the checkout flow for 1200 orders a day")] == ["40"]
    assert invented(source, "Fixed bugs in the checkout flow for 1200 orders a day") == []


def test_invented_names_urls_and_emails_are_caught():
    source = "Built a library app with Python and FastAPI"
    found = {(f.kind, f.value) for f in invented(source, "Built a library app with Python, FastAPI and Kubernetes at Google. See https://example.com or mail me@x.io")}
    assert ("name", "kubernetes") in found and ("name", "google") in found
    assert ("url", "https://example.com") in found and ("email", "me@x.io") in found
    assert not any(v in {"python", "fastapi"} for _, v in found)


def test_a_sentence_opening_capital_is_not_a_name():
    assert invented("made a tool for the team", "Developed a tool for the team.") == []


def test_keywords_in_the_output_that_the_facts_lack_are_reported():
    facts = "Skills: Python, SQL. Project: library app in FastAPI."
    out = "Backend developer with Python, SQL and Kubernetes experience."
    assert [f.value for f in unsupported_keywords(facts, out, ["python", "kubernetes", "docker"])] == ["kubernetes"]


# ---------------------------------------------------------------- keyword gap
JD = """We are hiring a Backend Developer. You will build REST APIs with Python and FastAPI, write SQL queries against PostgreSQL,
and deploy services with Docker. Experience with Python, REST APIs and PostgreSQL is required. Strong communication skills."""


def test_job_keywords_ignore_filler_and_rank_by_frequency():
    terms = dict(kw.job_keywords(JD))
    assert terms["python"] == 2 and terms["fastapi"] == 1 and "postgresql" in terms and "docker" in terms and "fastapi" in terms
    assert "strong" not in terms and "required" not in terms and "the" not in terms
    assert "rest apis" in terms  # a two-word phrase said twice, shown as the job description wrote it


def test_coverage_matches_plurals_and_reports_the_rest():
    covered = {k.term: k.present for k in kw.coverage(JD, "Built REST API services in Python. Wrote SQL queries. Used PostgreSQL.")}
    assert covered["python"] and covered["postgresql"] and not covered["docker"] and not covered["fastapi"]


def test_normalise_handles_plurals_and_symbols():
    assert kw.normalise("APIs") == "api" and kw.normalise("libraries") == "library" and kw.normalise("class") == "class"
    assert "c++" in kw.tokens("Experience with C++ and C#") and "c#" in kw.tokens("Experience with C++ and C#")


# ---------------------------------------------------------------- language rules
def test_action_verbs_and_numbers():
    assert starts_with_action_verb("Built a parser") and not starts_with_action_verb("Responsible for parser")
    assert is_quantified("Cut latency by 30%") and not is_quantified("Cut latency")


def test_language_issues():
    codes = {i.code for i in check_text("i worked on the the login page  and it was very good .")}
    assert {"REPEATED_WORD", "FIRST_PERSON", "DOUBLE_SPACE", "SPACE_BEFORE_PUNCTUATION", "FILLER", "LOWERCASE_START"} <= codes
    assert "WEAK_OPENING" in {i.code for i in check_text("Responsible for the login page")}
    assert check_text("Built the login page for 3 teams") == []
    assert check_text("   ") == []
