# Certificate Service API

Base URL `/api/v1` (port 8009). The machine-readable contract is [openapi.json](openapi.json) (17 operations).
Conventions are the platform's ([lms-backend/README.md](../../README.md)): bearer token from user-management, ids are
64-bit numbers as strings, success `{status, code:"SUCCESS", message, <resource>}`, errors `{status:"error", code,
message, details[], request_id}`.

## Who may do what

| Caller | Can |
|---|---|
| **Anyone** | `GET /public/verify/{code}` |
| **Student** | list/read their own certificates, download the PDF |
| **Institution staff / head** | list/read/download their institution's students' certificates, details and audit trail |
| **Exam manager** (`exams.manage`) | all certificates, revoke, regenerate a PDF |
| **Template author** (`content.author`) / **reviewer** (`content.review`) | write / activate and archive templates |

## Certificates

- `GET /certificates?course_id&user_id&status&pdf_status&sort_order&page&per_page` — scoped by role.
- `GET /certificates/export?course_id&status` (staff, exam managers) — the same certificates as the list, as CSV (UTF-8 with BOM), at most 10,000 rows, newest first. `403` for students.
- `GET /certificates/{id}` — includes `verification_url`, `linkedin_add_url`, `pdf_status` (`pending` → `ready`, or `failed`).
- `GET /certificates/{id}/download` → `{url, filename, expires_in}` (a short-lived presigned S3 link). `409 PDF_NOT_READY`
  while rendering; `403 CERTIFICATE_REVOKED` for a student once revoked.
- `POST /certificates/{id}/revoke {reason}` (exam manager) — `409 ALREADY_REVOKED` the second time.
- `POST /certificates/{id}/regenerate-pdf` (exam manager).
- `GET /certificates/{id}/details`, `GET /certificates/{id}/events` (staff) — attempt id, revoke reason, PDF attempts and
  last error; the audit trail (`issued`, `pdf_ready`, `pdf_failed`, `pdf_regenerate_requested`, `revoked`).

## Public verification

`GET /public/verify/{code}` (no token; 60 requests/min/IP, then 429). `code` is the `verification_code` in the QR code.

```json
{"status": "success", "code": "SUCCESS", "message": "This certificate is valid.",
 "verification": {"valid": true, "status": "issued", "certificate_id": "…", "student_name": "Aarav Reddy",
   "course_title": "Full Stack Development with MERN", "institution_name": "Springfield High", "issuer": "LMS",
   "completion_date": "2026-09-21T10:30:00Z", "grade": "Distinction", "score_percent": 91.5, "issued_at": "…"}}
```

A revoked certificate answers `valid: false, status: "revoked"` with `revoked_at`, and never the reason. An unknown code is 404.

## Templates

`POST /certificate-templates {name, course_id?, title_text, body_text?, footer_text?, accent_color, signatories[≤3], grade_bands[]}`
creates a draft (`course_id` empty = the platform default). `PATCH` edits a draft only; `POST /{id}/activate` and
`/archive` need `content.review`; `GET /certificate-templates?course_id&status`; `GET /certificate-templates/{id}/preview` returns a sample PDF.

- `body_text` / `footer_text` placeholders: `{student_name} {course_title} {completion_date} {institution_name}
  {score_percent} {grade} {issuer} {certificate_id}` (anything else is `422 INVALID_PLACEHOLDER`).
- `grade_bands`: `[{"min_percent": 85, "label": "Distinction"}, …]`, the lowest must start at 0. Default: Distinction ≥ 85,
  Merit ≥ 70, Pass.
- Resolution when a certificate is issued: the course's active template, else the platform default's, else the built-in.
  The certificate keeps a snapshot; later template changes never alter it.
