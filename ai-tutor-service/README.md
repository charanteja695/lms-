# AI Tutor Service

> Status: **Done** · Roadmap phase: **7** · Local port: **8011** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md) §5.5

A course-grounded learning tutor and a support assistant in one service: answers from the student's own course with
citations, gives hints before solutions on practice problems, is switched off inside graded tests, hands the student to a
person when it should, and lets staff curate a FAQ and authors measure how well retrieval finds the right lesson. It calls
[ai-gateway](../ai-gateway/) for every model and embedding — it holds no provider key.

| | |
|---|---|
| Owns (own database) | conversations, messages, feedback, hint_progress, escalations, content_chunks (vectors), index_jobs, faq_entries, eval_sets/cases/runs; read-models: course_version_refs, item_refs, enrollment_refs, attempt_refs, certificate_refs; outbox_events, processed_events |
| Emits events | `tutor.escalated`, `tutor.feedback` |
| Consumes events | `course.published`, `course.retired` (catalog) · `transcript.ready` (media — contract only, not emitted yet) · `enrollment.created/removed` (learning) · `attempt.started/submitted/finalized` (assessment) · `certificate.issued/revoked` (certificate) |
| Calls | ai-gateway (completions, embeddings) · support-service (open a ticket) — both with the shared internal token |
| API | [docs/API.md](docs/API.md) · [docs/openapi.json](docs/openapi.json) (30 operations) |

## What a turn does (`app/services/tutor_service.py`)

Everything that must hold *whatever a model says* is decided in code, before a model is asked, and the model is only told
the outcome. In order:

1. **Graded test in progress → refused** (`403 TUTOR_DISABLED_IN_TEST`), nothing saved, nothing sent anywhere. Driven by
   `attempt.started/submitted` events; a practice test does not block; a lost `submitted` event cannot lock a student out
   (the block ends at the attempt's deadline plus a grace period); events arriving out of order never move an attempt backwards.
2. The student's message is **saved** first, so a failure later never loses it, and an `Idempotency-Key` makes a retry return the
   same answer (or finish the same turn) instead of asking twice.
3. **A request for a person, or money / integrity / access → escalation, no model call.** First-person phrasings escalate in any
   conversation; the support assistant also matches looser wording. A course *about* payment gateways is not a billing problem.
4. **Hint ladder** for a practice problem — `hint_progress` is per student and item, server-side and monotonic: each hint request
   climbs one rung (nudge → approach → pseudocode → full solution, the last only after three hints). "Just give me the
   solution" cannot skip a rung; the prompt is *told* the level, never asked to decide it.
5. A **published FAQ answer** that matches closely (≥ `FAQ_DIRECT_ANSWER_AT`) is returned as-is — no model call, no cost.
6. **Low confidence** — nothing relevant retrieved and no code/lesson context — says so; a second miss in a row escalates.
7. Otherwise the model answers from **numbered sources** (retrieved passages, plus the lesson the student has open), FAQ entries
   and, for support, **read-only facts** about the student's own enrolment, attempts and certificates. The answer's `[n]`
   citations are resolved to the lesson (and video timestamp); if the model cites nothing, the best source is attached as an
   *implicit* citation, so every answer names where it came from.

No transaction is held open across a call to ai-gateway. Tools are **not** offered to the model: the read-only lookups are made
by this service from its own event-built read-models, chosen from the question, so there is no model-driven path to a write
action or to another student's data.

## Retrieval (RAG) and the content index

- `course.published` (catalog-service, extended with titles and note text for this service) is **chunked in the consumer's
  transaction**; a worker job then **embeds** the chunks that have no vector, in batches, leased with `SKIP LOCKED` and retried
  with backoff. Until embedded, a chunk is found by the **lexical fallback** (idf-weighted word overlap) — and so is everything
  when the embedding service is down; the method used is stored on every answer (`retrieval: dense | lexical`).
- Vectors are JSON and compared in-process with numpy over one course version's chunks (cached per version, rebuilt when a probe
  says the chunks changed). Fine for a course (hundreds to low thousands of chunks); pgvector is the next step (D5).
- Video **transcripts** become timestamped windows via `transcript.ready` — a contract (`{"media_asset_id", "segments":
  [{"start","end","text"}]}`) that media-service will emit; it has no transcripts yet, so today only notes and practice text are
  searchable. `course.retired` retires a version's chunks; `POST /index/reindex` re-embeds after a model change.

## Escalation to support

An `Escalation` row is the durable job, written in the same transaction as the student's message; the student is told at once.
The worker writes a hand-off note (a model summary via ai-gateway, or a plain fallback), opens the ticket in support-service with
the escalation id as the `Idempotency-Key` (a retry after a timeout never opens two), retries with backoff, and marks it `failed`
after `ESCALATION_MAX_ATTEMPTS` for a support manager to retry. `tutor.escalated` is emitted when the hand-off is recorded.
Routing: `learning` goes to the batch's staff, the rest to platform support — support-service decides from the category.

## FAQ, feedback and evaluation

- **FAQ** — draft → publish; scopes platform / organization / course; institution staff write for their own institution, course
  authors for a course, support managers for everything. Staff **promote** a tutor answer to a draft (edit before publishing); a
  thumbs-up on an FAQ answer ranks that entry higher for others.
- **Feedback** — thumbs up/down per answer (`tutor.feedback`); authors see totals per course and the downvoted Q&A without who asked.
- **Offline evaluation** — an author writes questions and names the lesson(s) that answer each; a run measures **hit@k and MRR of
  the retriever** against the current index (dense or lexical, stated). It grades retrieval, not the wording of a model's answer
  — an offline set cannot grade that without a judge model.

## Prompts

`tutor.learning`, `tutor.support` and `tutor.escalation_summary` are registered in ai-gateway's prompt registry:
`python -m app.cli register-prompts --gateway-url … --token <an AI manager's token>` creates them as **drafts**; a *different* AI
manager must activate each (the gateway refuses self-activation). Until then every completion answers `503 TUTOR_UNAVAILABLE`.

## Run

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pip install -e ../shared --config-settings editable_mode=compat   # so mypy can see lms_common
cp .env.example .env && alembic upgrade head
uvicorn app.main:app --port 8011          # API
python -m app.worker                      # outbox relay, event consumer, indexing, escalation delivery, housekeeping
pytest -m "not postgres"                  # 127 tests (SQLite, fakeredis, mocked gateway and support-service)
pytest -m postgres                        # 6 tests on a real embedded PostgreSQL (pip install pgserver)
```

## Verification (2026-09-24)

**134 tests** — 44 unit (chunking, transcript windows, cosine/lexical scoring, escalation and hint-ladder rules, the blocking
window, history assembly), 83 integration on SQLite, **6 on a real PostgreSQL** (migration up → down → up with `alembic check`
finding no drift; JSON null stored as SQL NULL; concurrent workers never claim the same index job or escalation; concurrent messages
in one conversation get consecutive numbers; concurrent hint requests climb the ladder exactly once each). ruff and `mypy --strict` clean.

### Not built / not verified

- **Not exercised anywhere on this machine:** a real Redis, and — through ai-gateway — any real model or embedding provider. The
  gateway and support-service are mocked to their contracts (`httpx.MockTransport`); retrieval quality was tested with a
  bag-of-words stand-in for embeddings, so **no claim is made about real embedding relevance**. The score thresholds
  (`MIN_RELEVANCE`, `LOW_CONFIDENCE_BELOW`, `FAQ_DIRECT_ANSWER_AT`) are starting values to tune per embedding model with the evaluation sets.
- **Video transcripts are not searchable yet** (media-service emits no `transcript.ready`), so a question answered only in a video
  cannot be grounded; the tutor says it could not find it.
- **Escalation and sensitive-topic detection are keyword rules**, not a classifier; misses and false positives are possible
  (tested for the obvious ones). Prompt-injection defence is structural (data is labelled, no tools, guardrails in code), not proven
  against a determined attacker.
- **No live human-agent chat**, no push notification of a support reply (notification-service is not wired to `tutor.escalated`
  yet), no per-institution tutor on/off switch (ai-gateway's per-org quota `enabled` flag is the switch), no voice.
- Conversations are hard-deleted `CONVERSATION_RETENTION_DAYS` after creation (and a week after a student deletes one); the ticket
  keeps its own copy of the hand-off note. Downvoted-answer review shows the question and answer text to authors (not who asked) —
  the text itself is unredacted student input.
