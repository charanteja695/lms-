# Career Service API

Base URL `/api/v1` (port 8013). Machine-readable contract: [openapi.json](openapi.json) (33 operations). Platform conventions
([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are 64-bit numbers as strings, success
`{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code, message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Student** | their own profile, items, resumes, versions, ATS, AI suggestions, exports, share links |
| **Institution staff / head** | `GET /students/{id}/profile` for students of their own institution (read only) |
| **Careers manager** (`careers.manage`) / super admin | `GET /students/{id}/profile` for any student |
| **Anyone** | `GET /public/resumes/{token}[/pdf]` for a live share link |

## Profile — `/profile`

- `GET /profile` → `{profile: {headline, summary, phone, location, links[{label,url}], target_roles[], revision}, personal: {name, email, name_verified},
  items[]}`. An item: `{item_id, kind, verified, label: "Verified"|"Self-declared", source, active, data, derived, position, inactive_reason}`.
  `derived` holds what is worked out on read: `course_title`, and for a `skill_score` the `percentile` (null below the cohort minimum) and `cohort_size`.
  A revoked certificate stays listed with `active: false` and a reason, and never reaches a resume.
- `PATCH /profile` any of `headline, summary, phone, location, links (≤6), target_roles (≤5)`.
- `POST /profile/items {kind, data}` — `kind`: `education | experience | project | skill | achievement`
  (`403 VERIFIED_KIND` for certificate, course, skill_score; `409 TOO_MANY_ITEMS` at 50 per kind). `data` by kind (unknown keys are rejected):
  - education `{institution, degree, field_of_study?, grade?, start_date?, end_date?, bullets?[≤8]}`
  - experience `{company, title, location?, current?, start_date?, end_date?, bullets?[≤8]}`
  - project `{name, url?, technologies?[≤20], description?, start_date?, end_date?, bullets?[≤8]}`
  - skill `{name, category?}` · achievement `{title, date?, description?}`
  Dates are `YYYY-MM`; an end before a start is `INVALID_DATE_RANGE`; a bullet is ≤300 characters. Errors name the field as `data.<field>`.
- `PATCH /profile/items/{id} {data}`, `DELETE /profile/items/{id}` — own entries only; `403 VERIFIED_ITEM_READONLY` on a verified one.
- `PUT /profile/items/order {kind, item_ids[]}` — every item of the kind exactly once (`409 INVALID_ORDER`).
- `GET /students/{user_id}/profile` — the same shape, read only (staff of the student's institution, careers managers).

## Resumes

- `GET /resume-templates` → `classic`, `compact`, `modern` (all `ats_safe`).
- `POST /resumes {title, target_role?, template_key?, job_description?, blank?}` — starts from the whole profile in a sensible order
  (education, projects, experience, skills, certificates, scores, achievements; completed courses hidden) unless `blank`. `409 TOO_MANY_RESUMES` at 10.
- `GET /resumes` (paged), `GET /resumes/{id}` → `{resume, job_description, draft, document, ats}`.
  A resume: `{resume_id, title, target_role, template_key, draft_revision, latest_version_no, shared, share_expires_at, created_at, updated_at}`.
- `PATCH /resumes/{id} {expected_revision, title?, target_role?, template_key?, job_description?, draft?}` — `409 STALE_DRAFT` if `expected_revision` is not the current
  one. The draft: `{summary: {text?, visible}, personal: {show_phone, show_location, show_links}, sections: [{key, title?, visible, items: [{item_id, bullets?}]}]}`; section
  order is list order. `422` details: `UNKNOWN_ITEM`, `WRONG_SECTION`, `DUPLICATE_ITEM`, `VERIFIED_ITEM_READONLY` (bullets on a verified item or a skill).
- `POST /resumes/{id}/duplicate`, `DELETE /resumes/{id}` (its share link stops working).
- **Versions:** `GET /resumes/{id}/versions`, `POST /resumes/{id}/versions {label?, note?}` (newest 50 kept; a shared one is never pruned),
  `GET /resumes/{id}/versions/{n}` (with its frozen `document`), `POST /resumes/{id}/versions/{n}/restore` (saves the current draft first).

## Scoring and checks

- `POST /resumes/{id}/ats {job_description?}` → `{score, word_count, components[{key,label,points,max,detail}], fixes[{code,severity: high|medium|low,message,section,item_id}], keywords[]}`.
  Uses the request's job description, else the one saved on the resume.
- `POST /resumes/{id}/keyword-gap {job_description?}` → `{match_percent, keywords[], add_from_profile[], not_in_profile[], advice}` (`422` with no job description anywhere).
- `POST /resumes/{id}/grammar` → `{issues[{where, item_id, code, severity, message, excerpt}]}` over the summary and the student's own bullets (rule-based).

## AI suggestions (through ai-gateway)

Each returns a suggestion `{text, applicable, warnings[{type: number|url|email|name|keyword, value}], language_issues[]}`; nothing is saved.
`applicable: false` means the text contains something not in the student's facts.

- `POST /resumes/{id}/ai/summary {tone?: professional|warm|concise}` (`422 NO_FACTS` on an empty profile).
- `POST /resumes/{id}/ai/rewrite {bullets[1..8], context?}` → `suggestions[{original, text, applicable, warnings, metric_prompt}]`; a bullet without a number gets a *prompt* to add one,
  never an invented one. `503 AI_BAD_OUTPUT` if the model's answer is not one line per bullet.
- `POST /resumes/{id}/ai/polish {text, tone?}`.
- `POST /resumes/{id}/ai/tailor {job_description?, include_summary?}` → `{gap, summary}`; the gap is rule-based; the summary (a model call) only when asked.
- Errors: `429 QUOTA_EXCEEDED`, `403 AI_DISABLED`, `503 AI_UNAVAILABLE`, `422 AI_CONTENT_BLOCKED`. Rate limited per student.

## Export and sharing

- `GET /resumes/{id}/export/pdf?version_no=` — `application/pdf`; header `X-Unrenderable-Characters` counts characters outside Latin-1 (printed as `?`).
- `GET /resumes/{id}/export/json-resume?version_no=` — [JSON Resume](https://jsonresume.org/schema) with an `x-lms.verified_items` block.
- `POST /resumes/{id}/share {version_no?, expires_in_days?, show_contact?}` → `{share: {token, url_path, version_no, expires_at, show_contact}}`. Pinned to a version (a fresh
  snapshot by default); contact details hidden unless `show_contact`; a new link replaces the old. `DELETE /resumes/{id}/share` revokes (204).
- `GET /public/resumes/{token}` → `{resume: <JSON Resume>, document, version_no}` · `GET /public/resumes/{token}/pdf`. No login; unknown, revoked, expired and deleted are all
  `404 SHARE_NOT_FOUND`; `X-Robots-Tag: noindex, nofollow`; `429` per address.

## Events

`skill_profile.updated` `{user_id, organization_id, revision, headline, target_roles, verified: {certificate, course, skill_score}, self_declared: {education, experience, project, skill, achievement}, occurred_at}`
(counts of active items). `resume.updated` `{resume_id, user_id, organization_id, action: version_saved|restored|shared|unshared|deleted, version_no, target_role, occurred_at}` (`ats_score` on `version_saved`).
Consumed payload contracts are in `app/events/consumers/handlers.py`.
