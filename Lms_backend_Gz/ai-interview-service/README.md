# AI Interview Service

> Status: **Done** · Roadmap phase: **10** · Local port: **8015** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.8

AI-conducted interviews for practice and hiring. A plan's core questions are fixed and asked to every candidate verbatim; the model only
proposes follow-ups, and a deterministic director — never the model — decides what is asked next, by the server's clock. Speech (STT/TTS)
and a live compiler run through other services so text always works even when they do not. Scoring verifies every quote against the
transcript, clamps scores that lack evidence, and computes the recommendation from the weighted rubric — the model never chooses it. A
hiring interview's result always needs a person's review before a candidate ever sees it; appeals are decided by someone else and an
upheld one grants a retake; calibration against human-rated samples and a four-fifths fairness audit are built in.

| | |
|---|---|
| Owns (own database) | interview_plans, interviews, interview_turns, evaluations, appeals, calibration_samples, calibration_runs, work_items; read-models: org_refs, user_refs; outbox_events, processed_events |
| Emits events | `interview.invited`, `interview.started`, `interview.finished`, `interview.expired`, `interview.cancelled`, `interview.evaluated`, `interview.reviewed`, `interview.appealed`, `interview.appeal_decided` · `interview.completed` (the contract job-portal-service consumes to complete a hiring pipeline's interview stage) |
| Consumes events | `user.*`, `institution.*`, `employer.*` (user-management) · `application.stage_changed` (job-portal-service — `to: ai_interview_invited` invites the candidate; an ended application cancels an unstarted invitation) · `integrity.decided` (proctoring-service — contract only: nothing arrives until it is extended to interviews) |
| Calls | ai-gateway (`interview.conduct`, `interview.evaluate`, `interview.feedback` completions; `/internal/transcriptions`, `/internal/speech` — contract only, see Known limits) · code-execution-service (`POST /internal/runs`) — both with the shared internal token |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (36 operations) |

## The rules that shape the design

1. **The AI only recommends; the recommendation is computed, not chosen.** `app/evaluation/rubric.py` turns the model's per-round scores
   and quotes into a recommendation from the plan's weights and the configured thresholds (`STRONG_YES_AT` > `YES_AT` > `LEAN_NO_AT`) —
   the model is never asked for a verdict and its answer is never used as one.
2. **Every score needs evidence, and evidence is checked, not trusted.** A quote must appear, word for word (ignoring case and spacing),
   in something the candidate actually said; a quote that does not is dropped and counted in `invalid_quotes`. A score of 1, 2, 4 or 5
   lacking `MIN_EVIDENCE_FOR_EXTREME_SCORE` verified quotes is clamped to 3. A coding round's code-quality score is forced to 1 if the
   candidate never ran code, whatever the model said.
3. **The same interview for everyone.** A plan's core questions are fixed at publish time and asked in order, verbatim, to every
   candidate; publishing freezes it and a new version is a new row (`family_id` links them). An interview freezes a `plan_snapshot` at
   creation, so a later version never changes an interview already in progress or scored.
4. **A deterministic director, not the model, decides the flow** (`app/conduct/director.py`): the model only proposes a follow-up text;
   whether it is asked (a limit per question), or the interview moves to the next question, the next round, or wraps up, is decided by
   plain state and the server's clock. If the model cannot answer, the interview does not stop — the next core question is asked and the
   turn is marked `degraded`.
5. **A person must decide a hiring result.** `interview_service.py`'s state machine has no path from `evaluated` to a candidate reading a
   screening report; `review_service.py`'s `review` (confirm or override, with a required note when overriding) is the only way there.
   An appeal is decided by someone other than whoever reviewed it (a careers manager may always); upholding it grants a retake.
6. **Protected attributes never enter a decision.** This service holds a user id, a role and an organization id for reference only — no
   name, photo, gender or similar reaches a prompt or a score. The fairness audit's only grouping attribute is the candidate's
   institution, the one this service has, and it skips groups smaller than `AUDIT_MIN_GROUP`.

## What is where

- **Plans** (`plan_service.py`, `app/conduct/plan_rules.py`): a screening plan belongs to an employer (recruiters/admins write it); a mock
  plan belongs to the platform (careers managers write it). Rounds (intro, technical, coding, system-design — senior only, behavioural)
  carry core questions, a coding round's allowed languages, and the rubric criteria they are scored on; the criteria weights default to
  equal and must sum to 1. Draft → published (immutable; interviews from here on freeze it) → retired; `POST …/versions` starts a new
  draft from a published one.
- **Getting an interview** (`interview_service.py`): a student's mock practice is within a monthly allowance and only one may be open at
  a time; a screening interview is created from `application.stage_changed` (idempotent per application, the newest published version of
  the job's plan). Consent (versioned; recording required for a `strict`-proctored plan) then start — the server sets `ends_at` from the
  plan's duration and nothing the client sends can move it.
- **Conducting it** (`conduct_service.py`): a turn is two short transactions around one slow call — the answer is saved and the interview
  marked `awaiting_reply_since` (so a second answer cannot interleave; the DB row lock makes a same-key retry replay instead of duplicate,
  proven under real PostgreSQL concurrency in `tests/integration/test_postgres.py`), committed, the model is asked for a follow-up, and
  the director decides what happens next. Coding-round code runs through code-execution-service and both the code and its output land in
  the transcript. Speech is best effort through ai-gateway; a candidate can always type instead.
- **Evaluating** (`evaluation_service.py`, `app/evaluation/rubric.py`): run by the worker once an interview completes. A candidate who
  answered nothing is not sent to the model. A model that is down is retried with backoff; one that keeps failing leaves the evaluation
  `failed`, visible to the recruiter, who can ask for a re-run (`POST …/evaluate`). A practice interview also gets a candidate-facing
  improvement plan.
- **Review and appeals** (`review_service.py`): `POST …/employer/interviews/{id}/review` confirms or overrides the AI's recommendation and
  can release the candidate's feedback. The candidate's own report never carries a recommendation — a hiring decision is read from the
  employer's side, by a person, never inferred from the practice-report shape. An appeal needs released feedback and is within
  `APPEAL_WINDOW_DAYS`; deciding it needs a different reviewer; upholding it grants exactly one retake.
- **Calibration and the fairness audit** (`audit_service.py`, `app/evaluation/audit.py`): human-rated samples are scored with the current
  prompt and plan and compared (mean absolute error, share within one point, recommendation agreement). The audit reports the
  recommendation mix, the override rate, evidence quality, and the four-fifths comparison of advance rates across the candidates'
  institutions, flagging any group under 80% of the best group's rate.
- **Worker** (`app/worker/`): the outbox relay, the `lms:events` consumer (`app/events/consumers/`), the durable work queue (`EVALUATE`,
  `CREATE_SCREENING`, leased with `SKIP LOCKED`, retried with backoff), a sweep that ends interviews whose time ran out and expires unused
  invitations, and housekeeping.

## Running

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
pip install -e ../shared --config-settings editable_mode=compat   # what mypy needs to see lms_common's types
alembic upgrade head && uvicorn app.main:app --port 8015
python -m app.worker        # outbox relay, event consumer, evaluation/screening work, sweeps, housekeeping
python -m app.cli register-prompts --gateway-url http://localhost:8010 --token <an AI manager's token>   # then a different AI manager activates the interview.* prompts
```

Docker: `docker compose up ai-interview-service-migrate ai-interview-service ai-interview-service-worker` from `lms-backend/`.

## Verified

`ruff` and `mypy --strict` clean; **76 tests**: unit (plan validation and rubric weight normalisation, the director's next-question/
follow-up/round/wrap-up logic including a blank follow-up, the rubric's quote verification and score clamping, calibration metrics and the
four-fifths comparison) and integration over SQLite (plan lifecycle and every validation rule, permissions per kind and per company, a
full mock interview end to end incl. evaluation and a report that never carries the recommendation, a model-proposed follow-up, a
degraded turn when the model is down, idempotent turn retry, speech-unavailable 503, the coding round and its transcript, a time-up
sweep, screening creation from an event and its idempotency, an ended application cancelling an invitation, mandatory human review and
the note-required override, appeals incl. the second-reviewer rule and the granted retake, a failed evaluation re-run, calibration sample
validation and a run, the fairness audit's grouping and flag), plus PostgreSQL through an embedded server (`pgserver`): migration
up→down→up with no drift from the models, twelve work items claimed by six workers → each once, and two identical concurrent turn
submissions (same Idempotency-Key) → one recorded turn, proven under real row locking, not simulated.

**Not exercised:** real Redis (fakeredis), Docker at runtime, a live user-management token round trip, the real Anthropic API (ai-gateway
is mocked at its HTTP contract, so interview and evaluation prompt quality are unjudged), the real code-execution-service HTTP (mocked to
its documented contract), and real speech-to-text/text-to-speech (ai-gateway's `/internal/transcriptions` and `/internal/speech` are
routing contracts only — see [ai-gateway's README](../ai-gateway/README.md) — so this service's speech path is exercised against that
contract, never against a real provider).

## Known limits

- **Speech is contract-only.** Until ai-gateway wires a real STT/TTS provider, every audio turn and every `want_audio` reply answers
  `SPEECH_UNAVAILABLE` in a real deployment; text always works, by design, so this is a degradation, not a missing feature.
- **No audio recording is stored.** A `strict`-proctored plan requires the candidate to *consent* to recording; this service does not
  itself capture or retain audio/video — that is proctoring-service's job, once it is extended to interviews (see `integrity.decided`).
- **`integrity.decided` is a contract.** proctoring-service emits it for assessment attempts today, not interviews; `integrity_status`
  and the recommendation cap it drives are wired and tested, but nothing arrives until proctoring-service is extended.
- **A retake does not re-enter the hiring pipeline automatically.** `POST …/retake` creates a fresh interview attempt; job-portal-service
  is not told a retake happened (no event for it yet), so an employer relying on that pipeline needs to notice the retake and follow up.
- **The rubric thresholds and weights are configured defaults**, not validated against real hiring outcomes; `run_calibration` measures
  agreement with human raters but nothing here recalibrates thresholds automatically.
- **The fairness audit's only grouping attribute is the candidate's institution** — the one thing this service holds about who a
  candidate is. It cannot audit by any attribute it never receives, by design (see rule 6 above).
- No notification delivery: every `interview.*` event is emitted for notification-service to consume, not delivered directly.
