# AI Interview Service API

Base URL `/api/v1` (port 8015). Machine-readable contract: [openapi.json](openapi.json) (36 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | mock-interview plans, their own interviews (consent, take, run code, end), their own report (a screening report once released), appeal, retake |
| **Recruiter / employer admin** | their company's screening plans and interviews: transcript + evaluation, review (confirm/override), re-evaluate, appeals, calibration and the fairness audit |
| **Careers manager** (`careers.manage`) | the platform's mock plans; read/act on any company's screening plans, interviews, calibration and audits |

## Interview plans — `/interview-plans`

`POST` a draft: `{kind: mock|screening, title, role, skills[], difficulty: easy|medium|hard|senior, duration_minutes, rounds[], criteria_weights?, instructions?, proctoring_level?, max_attempts?, retake_cooldown_days?}`.
A screening plan needs a recruiter/admin (owned by their employer); a mock plan needs a careers manager (owned by the platform).
- `rounds[]`: `{type: intro|technical|coding|system_design|behavioural, minutes, questions[], languages[] (coding only), criteria[]?}` — `questions[]` are the
  core questions, asked to every candidate verbatim and in order; `criteria` defaults to the round type's usual ones. `system_design` needs `difficulty: senior`.
  Rounds' minutes must not exceed `duration_minutes`; `criteria_weights` (if given) must cover exactly the criteria the rounds use and sum to 1.
- `GET` (list, `kind`, `status`), `GET /{id}`, `PATCH /{id}` (draft only; `409 PLAN_NOT_DRAFT`), `POST /{id}/publish` (freezes it; retires the family's
  previous published version), `POST /{id}/retire`, `POST /{id}/versions` (a new draft, one version higher; `409 DRAFT_EXISTS` if one is already open).
- `GET /student/mock-plans` — published mock plans a student may practice with.

## Taking an interview (student) — `/student/interviews`

- `POST {plan_id}` → `201` a practice interview (`429 MOCK_QUOTA_EXCEEDED`, `409 INTERVIEW_ALREADY_OPEN`). A screening interview is created from the
  hiring pipeline's event instead (see Events) — this endpoint is mock only.
- `GET` (list mine, `status`, `kind`), `GET /{id}`, `GET /{id}/transcript` (the conversation so far, for a reloaded page; never the evaluation). An interview carries `current_round {key, type, minutes, languages, number, total}`.
- `GET /{id}/consent` → `{version, text, recording_required, instructions}` · `POST /{id}/consent {version, recording}` (`409 CONSENT_VERSION_CHANGED`,
  `RECORDING_REQUIRED`) · `POST /{id}/start` (`409 CONSENT_REQUIRED`, `CONSENT_EXPIRED` — start within `START_GRACE_MINUTES` of consenting) → the opening
  turn. The server sets `ends_at` here; nothing the client sends moves it.
- `POST /{id}/turns {text, want_audio?}` — a typed answer; `POST /{id}/turns/audio` (multipart `audio`, `want_audio` form field) — a spoken one, transcribed
  through ai-gateway (`503 SPEECH_UNAVAILABLE` if speech is not configured or fails: type instead). Both take an `Idempotency-Key` header (a retry with the
  same key replays the same turn instead of recording a duplicate — proven under real concurrency, see the README). Returns `{turn, reply, finished,
  degraded, audio?, audio_type?, audio_error?}` — `reply` is the interviewer's next line (a follow-up or the next core question, decided by the director,
  never the model directly); `degraded: true` means the model could not answer and the director moved on regardless.
- `POST /{id}/code/run {language, source, stdin?}` — coding round only (`409 NOT_CODING_ROUND`, `422 LANGUAGE_NOT_ALLOWED`, `409 RUN_LIMIT`); runs through
  code-execution-service and records both the code and its output in the transcript.
- `POST /{id}/end` — ends early; queues the evaluation. `GET /{id}/time-left` → `{round_seconds_left, interview_seconds_left}` by the server's clock.
- `GET /{id}/report` → `{released, summary?, criterion_scores?, strengths?, improvements?, improvement_plan?}` — **never a recommendation**; a screening
  report is released only once a person has reviewed it (`release_feedback`); a mock report is released as soon as it is scored.
- `POST /{id}/appeal {reason}` — screening only, needs released feedback, within `APPEAL_WINDOW_DAYS` (`409 NOT_RELEASED`, `APPEAL_WINDOW_PASSED`,
  `ALREADY_APPEALED`). `POST /{id}/retake` — only after an appeal is upheld (`403 RETAKE_NOT_GRANTED`, `409 RETAKE_EXISTS`).

## Screening interviews (employer) — `/employer/interviews`

- `GET` (list, `status`, `application_id`, `job_id`) · `GET /{id}` → interview + full transcript + evaluation (rubric per round, criterion scores,
  overall, `recommendation`, summary, strengths, improvements, flags, quote counts).
- `POST /{id}/review {recommendation?, note?, release_feedback?}` — no `recommendation` confirms the AI's; one overrides it (`note` then required;
  `422` if omitted). This is the only way a candidate can ever see a hiring result.
- `POST /{id}/evaluate` — re-run a failed or outdated evaluation; runs on the worker.
- `GET /employer/appeals` — open appeals (with the interview) · `POST /employer/interviews/{id}/appeal/decide {uphold, note?}` — `note` required when
  denying; `403 SECOND_REVIEWER_REQUIRED` if the caller is who reviewed the interview (a careers manager may always decide).

## Calibration and the fairness audit — `/interview-plans/{plan_id}`

- `POST /calibration/samples {turns[], human_scores, human_recommendation}` — `turns[]` are the transcript shape (`seq, round, speaker, kind, text,
  elapsed_ms`; copy them from a past interview's transcript). `GET /calibration/samples`.
- `POST /calibration/runs` — scores every sample with the current model and prompt, compares with the humans' ratings (`409 NO_SAMPLES`,
  `EVALUATOR_UNAVAILABLE`) → `{samples, mean_abs_error, within_one_rate, recommendation_agreement, details[]}`. `GET /calibration/runs`.
- `GET /audit` → `{interviews, evaluated, recommendations, average_score, reviewed, override_rate, invalid_quote_rate, adverse_impact: {groups[],
  flagged_groups[], rule}, calibration}` — screening plans only (`409 NOT_SCREENING`); groups by the candidates' institutions, skipping any smaller
  than `AUDIT_MIN_GROUP`; a group under 80% of the best group's advance rate is flagged.

## Events

Emitted: `interview.invited {interview_id, plan_id, kind, user_id, application_id?, job_id?, employer_id?, expires_at}` ·
`interview.started {..., ends_at, proctoring_level}` · `interview.finished {..., reason}` (completed → queues evaluation) ·
`interview.expired` (unstarted invitation ran out) · `interview.cancelled {..., reason}` ·
`interview.evaluated {interview_id, plan_id, kind, user_id, recommendation, score}` ·
`interview.completed {..., application_id, job_id, employer_id, report: {summary, criterion_scores, strengths, improvements, flags, attempt_no}}` —
**the contract job-portal-service consumes**; only for a screening interview tied to an application ·
`interview.reviewed {..., ai_recommendation, final_recommendation, overridden, feedback_released}` ·
`interview.appealed {..., appeal_id}` · `interview.appeal_decided {..., appeal_id, decision, retake_granted}`.

Consumed payload contracts are in `app/events/consumers/handlers.py`: `user.*`/`institution.*`/`employer.*` keep local reference rows;
`application.stage_changed` with `to: ai_interview_invited` and an `interview_plan_id` enqueues a screening invitation, an ended application
(`rejected|withdrawn|offer_declined|placed`) cancels one nobody started; `integrity.decided` (contract only today — see README) sets
`integrity_status`, which caps a screening recommendation at `lean_no` if `invalidated`.
