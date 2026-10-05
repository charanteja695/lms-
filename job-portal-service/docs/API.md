# Job Portal Service API

Base URL `/api/v1` (port 8014). Machine-readable contract: [openapi.json](openapi.json) (55 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | browse/search jobs, see eligibility and matches, recommendations, preferences, apply, follow and withdraw, answer offers |
| **Recruiter** | their company's jobs (draft, submit, pause, close) and those jobs' applicants: ranking, shortlist, confirmed rejection batches, stages, notes, offers, placement; attach jobs to a drive |
| **Employer admin** | everything a recruiter does, plus the company profile and answering a drive invitation |
| **Institution staff / head** | their students' applications, placements, numbers, drives (the head also invites companies) |
| **Careers manager** (`careers.manage`) | verify/suspend companies, approve jobs; read (never decide) any company's hiring |

## Companies

- `GET /employer/profile` (recruiter+) · `PATCH /employer/profile {about, website, industry, company_size, headquarters}` (admin) ·
  `POST /employer/profile/submit` (admin; needs about, website, industry) → `status` `draft | pending | verified | rejected | suspended`, `review_note`.
- `GET /companies/{id}` — a verified company's public profile (its own team and managers also see it while under review).
- `GET /admin/employers?status=pending` · `POST /admin/employers/{id}/review {approve, note}` (a rejection needs a note) ·
  `POST /admin/employers/{id}/suspend {note}` (pauses its open jobs) · `POST /admin/employers/{id}/reinstate`.

## Jobs (employer side) — `/employer/jobs`

`POST` a draft: `{title, description, employment_type: full_time|internship|contract, location_type: onsite|remote|hybrid, locations[], experience_min_months,
experience_max_months, ctc_min, ctc_max, currency, required_skills[], preferred_skills[], openings, deadline_at, eligibility, pipeline}`.
- `eligibility`: `{graduation_years: {min?, max?}, certificate_course_ids[], min_scores: [{course_id, min_percent}], institution_ids[]}` — non-empty
  `institution_ids` restricts the job to those institutions' students.
- `pipeline`: `{assessment: {test_id, min_percent?}, ai_interview: {plan_id}, hr_interview: bool}` — a stage that is on cannot be skipped; one that is off cannot be entered.
- `GET` (list, `status`, `q`), `GET /{id}`, `PATCH /{id}` (`409 JOB_PENDING`, `JOB_CLOSED`, `PIPELINE_LOCKED`, `OPENINGS_BELOW_PLACED`),
  `POST /{id}/submit` (`409 EMPLOYER_NOT_VERIFIED`; `422` details for a missing skill/description, a past deadline, `UNKNOWN_COURSE`, `UNKNOWN_INSTITUTION`),
  `/withdraw-submission`, `/pause`, `/resume`, `/close {reason}`. A job also closes itself at its deadline and when placements reach its openings.
- `GET /admin/jobs` (oldest submission first) · `POST /admin/jobs/{id}/review {approve, note}` — approving opens the job and queues matching.

## Jobs (student side)

- `GET /job-board?q&location&employment_type&location_type&skill&min_ctc&eligible_only&sort=relevance|newest|deadline|pay&page&per_page` — open jobs from verified
  companies the student may see (public, or restricted to their institution). Each: the job, `company_name`, `eligibility_result {eligible, reasons[]}`,
  `match {score, explanation[], breakdown, method}` when one exists, `applied`, `application_id`.
- `GET /job-board/{id}` (stays readable after closing if the student applied) · `GET /recommendations` (best matches, highest first; empty while `open_to_work` is off).
- `GET/PUT /job-preferences {locations[], open_to_remote, roles[], min_ctc, employment_types[], open_to_work}` — changing them re-scores.

## Applications (student)

- `POST /job-board/{id}/apply {resume_id, cover_note?}` → `201`. `409 PROFILE_NOT_VERIFIED`, `403 NOT_ELIGIBLE` (reasons in `details`), `409 ALREADY_APPLIED`, `409 JOB_NOT_OPEN`,
  `409 DEADLINE_PASSED`, `422 RESUME_NOT_FOUND`, `409 RESUME_UNAVAILABLE`. The resume is frozen at this moment.
- `GET /applications?status`, `GET /applications/{id}` → status, match, assessment, offer, `history[]` (never the recruiter's notes or the screening).
- `POST /applications/{id}/withdraw {note?}` · `POST /applications/{id}/offer/respond {accept, note?}` (`409 OFFER_EXPIRED`, `NO_OPEN_OFFER`).

## The pipeline (recruiter)

- `GET /employer/jobs/{id}/applications?status&min_score&q&sort=screen|match|recent` · `GET /employer/jobs/{id}/funnel` · `GET /employer/applications/{id}`
  (the resume as sent, screening, assessment, interview, history, notes).
- `GET /employer/jobs/{id}/screening?shortlist_at&reject_below` — the AI's ranking of undecided applicants in buckets `shortlist | review | reject | unscreened`.
  **Nothing here changes any application.** `GET …/screening/decisions` — the audit log (model, prompt version, input digest, output).
- `POST /employer/jobs/{id}/applications/shortlist {application_ids[] | threshold}` (a recruiter's decision).
- `POST /employer/jobs/{id}/applications/reject {application_ids[], reason, confirm: true, threshold?}` → `201 {batch}` — the only way an application is rejected.
- `POST /employer/applications/{id}/transition {to, note?, hr_interview_at?}` (`to`: shortlisted, assessment_invited, ai_interview_invited, recruiter_review, hr_interview;
  `409 INVALID_TRANSITION`, `USE_DEDICATED_STEP`) · `POST …/advance` (the next stage of this job's pipeline; `NO_DEFAULT_STEP` where the next step is an offer) ·
  `POST …/notes {body}` · `POST …/offer {ctc, currency?, joining_date?, valid_days?, role_title?, note?}` · `POST …/place` (emits `candidate.placed`).
- Errors from the state machine: `APPLICATION_CLOSED`, `AI_CANNOT_REJECT`, `CANDIDATE_ONLY`, `SYSTEM_ONLY`, `EMPLOYER_SUSPENDED`.

## Institutions and drives

- `GET /institution/applications?status&drive_id` · `GET /institution/placements` · `GET /institution/summary {students_applied, applications, by_status, placed, placed_students, employers}`.
- `POST /drives {employer_id, title, description?, drive_date?}` (head; the company must be verified) · `GET /drives?status` · `GET /drives/{id}` (with numbers) ·
  `POST /drives/{id}/respond {accept}` (the company's admin) · `POST /drives/{id}/jobs {job_id}` (a recruiter; restricts the job to the institution) ·
  `POST /drives/{id}/complete` · `POST /drives/{id}/cancel` (closes its open jobs).

## Events

Emitted: `job.published {job_id, employer_id, title, location_type, locations, required_skills, visibility, drive_id, institution_ids, deadline_at}` · `job.closed {job_id, reason}` ·
`job.match_found {user_id, job_id, employer_id, title, score}` · `application.created {application_id, job_id, employer_id, user_id, organization_id, match_score}` ·
`application.screened {application_id, job_id, score, recommendation, source}` · `application.stage_changed {application_id, job_id, employer_id, user_id, from, to, actor, interview_plan_id?}` ·
`application.assessment_revised` · `offer.extended|accepted|declined|expired {offer_id, application_id, job_id, user_id, status, expires_at}` · `candidate.placed {application_id, job_id, employer_id, user_id, organization_id, title, ctc, currency}` ·
`placement_drive.*` · `employer_profile.verified|rejected`. Consumed payload contracts are in `app/events/consumers/handlers.py`.

## Directory — pickers

- `GET /directory/companies?q` — verified companies by name (any signed-in person; for a head inviting a company to a drive).
- `GET /directory/institutions?q` — active institutions by name (a company's team and careers managers; for restricting a job to institutions).
  Both read this service's own copy of the organisations (user-management lets a member list only their own), names only, 20 at most.
