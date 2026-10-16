# Job Portal Service

> Status: **Done** · Roadmap phase: **9** · Local port: **8014** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.7

Employers, jobs and hiring. Companies are verified by a platform admin before their jobs go live; jobs carry eligibility rules and a
hiring-pipeline template; students are matched (eligibility first, then a score with an explanation) and recommended jobs; an
application carries a frozen copy of the resume; AI screening ranks applicants but **only recommends**; a person confirms every
rejection; the pipeline runs through the hiring test, the AI interview and an HR round to an offer and a placement; institutions run
placement drives and follow their students' outcomes.

| | |
|---|---|
| Owns (own database) | employer_profiles, jobs, job_institutions, job_matches, candidate_preferences, applications, application_stages, application_notes, rejection_batches, ai_decisions, offers, placement_drives, work_items; read-models: org_refs, user_refs, course_refs, candidate_profiles, hiring_results; outbox_events, processed_events |
| Emits events | `job.published`, `job.closed`, `job.match_found` · `application.created`, `application.screened`, `application.stage_changed`, `application.assessment_revised` · `offer.extended/accepted/declined/expired` · `candidate.placed` · `placement_drive.proposed/accepted/declined/completed/cancelled` · `employer_profile.verified/rejected` |
| Consumes events | `user.*`, `institution.*`, `employer.*` (user-management) · `course.published` (catalog) · `skill_profile.updated` (career) · `attempt.finalized` for hiring tests (assessment) · `interview.completed` (ai-interview-service, phase 10) |
| Calls | ai-gateway (screening, embeddings) · assessment-service (`POST /internal/assignments`) · career-service (`POST /internal/resumes/{id}/snapshot`) — all with the shared internal token |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (55 operations) |

## The rules that shape the design

1. **The AI only recommends.** The state machine (`app/pipeline/machine.py`) forbids the *system* to reject; the screening's only
   status change is `applied → ai_screened`. A rejection is `POST …/applications/reject` with `confirm: true` — a person's confirmed
   batch, recorded with who, why, how many the screening had recommended rejecting and how many it had *not*.
2. **Protected attributes never reach a score.** Career-service's `skill_profile.updated` carries skills, technologies, role titles,
   months of experience, education level, graduation year, verified certificates and scores — no name, email, photo, date of birth,
   gender or institution name. Matching and the embedding text use only that. The model sees an anonymised summary
   (`app/screening/rules.py`): no name, email, phone, links, years or institution; the resume contributes only the work it describes,
   scrubbed. A test asserts none of those strings is in the request.
3. **Every AI decision is logged** (`ai_decisions`): model, prompt version (ai-gateway now returns it), input digest, the anonymised input as sent,
   the model's output and the final recommendation — for audit and bias review. `GET …/screening/decisions` reads it.
4. **Eligibility first.** Hard rules (graduation years, required certificates, minimum scores, institutions) decide who can be matched
   or apply; the reasons are shown ("Requires at least 90% in Python Programming (yours: 70%)").
5. **Only a person moves a person forward**; only the candidate withdraws or answers an offer; assessment and interview completion are facts
   from events, not clicks; an offer and a placement have their own steps.

## What is where

- **Company verification** (`employer_service.py`): draft → pending → verified | rejected; suspend / reinstate (an account suspension in
  user-management lifts itself on reactivation; an admin's does not). Suspending pauses the company's open jobs and freezes its pipeline.
- **Jobs** (`job_service.py`): draft → pending_approval → open → paused → closed. Submission needs a verified company and a complete job
  (a required skill, a real description, a future deadline, real courses and institutions). A careers manager approves or sends back with a reason.
  Editing something a match depends on re-scores an open job; the pipeline is locked once people apply; a job closes itself at its deadline
  and when placements reach its openings.
- **Matching** (`app/matching/`, `match_service.py`): score 0–100 = skills 50 (a declared skill earns 0.7 of its weight, one backed by a
  certificate or assessment result 0.85–1.0, more the higher the verified score) + semantic similarity 20 (embeddings when ai-gateway answers,
  word overlap when not; the method is stored) + relevant certificates 10 + preferences 20 (location, role, pay, kind; an unset preference earns
  half). Weights are settings that must add up to 100. Each match has an explanation ("Matches 6/8 required skills; missing: Docker, AWS").
  Matches are kept from `MATCH_STORE_MIN_SCORE`; a student is told (`job.match_found`) once per job, from `MATCH_NOTIFY_MIN_SCORE`.
  The work is durable and leased (`work_items`, `SKIP LOCKED`): a new/changed job is scored against candidates in batches, a changed profile or
  preference against the open jobs.
- **Applying** (`application_service.py`): needs a verified skill profile, eligibility, an open job before its deadline, no earlier application.
  The resume is frozen by career-service *outside* any transaction, and a failure there creates nothing.
- **Screening** (`screening_service.py`): rule-based fit (match score less 8 per red flag) plus, when ai-gateway answers, the model's score (averaged).
  When it does not — outage, quota, moderation, an unparseable reply — the rules stand alone and the result says `source: "rules"`.
- **Pipeline** (`machine.py`): `applied → ai_screened → shortlisted | rejected → assessment_invited → assessment_completed → ai_interview_invited →
  ai_interview_completed → recruiter_review → hr_interview → offered → offer_accepted | offer_declined → placed`, withdrawn at any stage. The job's
  template turns the optional stages on; one that is on cannot be skipped, one that is off cannot be entered.
- **Hiring test**: entering `assessment_invited` queues an invitation to assessment-service (retried with backoff; a refusal that can never succeed
  marks it `failed` and is noted in the history). A released `attempt.finalized` for that test completes the stage; a later higher `revision` (an integrity
  ruling) updates the result and is announced, never moving the application backwards or rejecting it.
- **Offers** (`offer_service.py`): from recruiter review (or the HR round); the candidate answers within `valid_days`; an unanswered offer expires and
  closes as declined; rejecting an application with an open offer withdraws it.
- **Placement drives** (`drive_service.py`): an institution's head invites a verified company; when its admin accepts, the company's jobs can be attached
  and become visible only to that institution's students. Staff and head follow applications, placements and numbers (never the employer's screening or notes).

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
alembic upgrade head && uvicorn app.main:app --port 8014
python -m app.worker        # outbox relay, event consumer, matching/screening/invitation work, offer expiry, deadline closing
python -m app.cli register-prompts --gateway-url http://localhost:8010 --token <an AI manager's token>   # then a different AI manager activates jobs.screen
```

Docker: `docker compose up job-portal-service-migrate job-portal-service job-portal-service-worker` from `lms-backend/`.

## Verified

`ruff` and `mypy --strict` clean; **107 tests**: unit (matching text/eligibility/score, the pipeline state machine incl. "the system can never reject")
and integration over SQLite (company verification, job lifecycle and validation, approval, deadline and suspension handling, matching and recommendations,
batches, preferences, notifications, embeddings vs word overlap, browse/search, applying and every refusal, frozen resume, screening incl. the
anonymised input, model failures and the audit log, ranking, shortlisting, confirmed rejection batches, the full pipeline with assessment/interview/HR,
revised assessment results, invitation failures, offers accept/decline/expire/withdraw, placement and auto-closing, drives, institution views),
plus PostgreSQL through an embedded server (`pgserver`): migration up→down→up with no drift from the models, the whole flow with the JSON/LIKE queries,
six simultaneous applications → one, twelve work items claimed by six workers → each once, six simultaneous answers to one offer → one, five
simultaneous rejection batches → one. (Postgres found a real bug the SQLite run could not: a `VARCHAR(8)` column too short for `shortlist`.)

**Not exercised:** real Redis (fakeredis), Docker at runtime, a live user-management token round trip, the real Anthropic/Voyage APIs (ai-gateway is
mocked at its HTTP contract, so screening prompt quality and embedding relevance are unjudged), the real assessment-service, career-service and
ai-interview-service HTTP (each mocked to its documented contract — ai-interview-service now exists and really emits `interview.completed` in
this shape, tested against on its own side; nothing here has been run against it live end to end).

## Known limits

- **Scores are heuristics, not validated.** The match weights, the "declared skill earns 0.7" rule, the word-overlap and embedding scalings, the
  screening blend and the recommendation thresholds are reasonable defaults that need calibration against real hiring outcomes and a bias audit.
  Rule-based screening cannot see beyond skills, titles, months and the described work.
- Skill matching is on normalised words and a small alias table, not meaning beyond what embeddings add to the semantic 20 points.
- A skill is "verified" when a course the student finished (certificate or passed assessment) has that word in its title: crude, and only as
  good as course titles. Career-service has no per-skill scores yet.
- Shortlisting by threshold is a recruiter action; there is no scheduled or automatic action of any kind on the AI's recommendation, by design.
- The institution's drive numbers and placement lists are counts and rows, not exports or dashboards (analytics-service's job).
- No notification delivery: `job.match_found`, `application.stage_changed` and `offer.*` are emitted for notification-service to consume.
- `resume.updated` is not consumed: the resume an application uses is frozen when the student applies.
- `integrity.decided` is not consumed directly: assessment-service folds integrity into `attempt.finalized` (a higher `revision`).
