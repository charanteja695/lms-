# Certificates module

> Status: **Done** · Backend: `lms-backend/certificate-service` · Roadmap: Phase 6
> Gated by the single `certificates` section (students, institution staff/heads, `exams.manage`, `content.author`, `content.review`); verification is public.

Three sections (see [src/modules/README.md](../README.md) for the layout rules):

- `issued/` — the certificate list (a student's own, an institution's students', or all for exam managers) and detail: download the PDF (short-lived link), copy the verification link, add to LinkedIn. Exam managers also regenerate the PDF and revoke (with a reason that is never shown publicly). Staff and exam managers see the issue details (attempt, render attempts, last error) and the audit trail; those two endpoints answer 403 to a student, so they are not requested for one.
- `templates/` — certificate templates: create a draft (a course's, or the platform default when no course is picked), edit it while it's a draft, preview a sample PDF, activate/archive (`content.review`), and copy an active or archived template into a new draft. The form lists the placeholders the service accepts; validation (placeholders, grade bands starting at 0, colour) is the server's.
- `verification/` — `/verify/:code`, the public page a certificate's QR code opens (matches the service's `PUBLIC_VERIFY_BASE_URL`). It works signed in or out and only shows the server's verdict.

**Nav:** one "Certificates" item. `common/pages/CertificatesHomePage` sends students, staff and exam managers to issued certificates, and an admin with only `content.author`/`content.review` (who gets a 403 on certificates) to templates. The certificates list links to templates for anyone who may see both.

Course titles on templates use `catalog/common`'s `CourseTitleCell`/`useCourseTitle`; the course picker reads catalog's course list, same as learning's batch form. Certificates themselves carry the student name and course title, so nothing else is resolved.

**Export:** staff and exam managers download the list as CSV (`GET /certificates/export`, same filters and reach as the list). PDFs open in a new tab (no in-page viewer).