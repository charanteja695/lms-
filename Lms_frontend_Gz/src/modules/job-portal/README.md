# Job portal module

> Status: **Done** · Backend: `lms-backend/job-portal-service` · Roadmap: Phase 8
> Gated by the single `job_portal` section (students; institution staff/heads; employer admins/recruiters; `careers.manage`).

One nav item, four sides — `common/pages/JobPortalHomePage` sends each person to theirs (`common/hooks/useJobRights` mirrors the service's `policy.py`):

- **Students** — `board/`: search and filter open jobs with the server's eligibility verdict (and reasons) and match score, recommendations, job preferences, and applying with a career resume (frozen at that moment; `board/api/boardApi.ts` reads `/resumes` itself, rule 5). `applications/`: status, history, assessment state, answering an offer, withdrawing.
- **Employers** — `employer/`: the company profile (admin edits and submits for verification), jobs (draft → submit for approval → open / paused / closed) with a form covering role, pay, skills, eligibility (certificate courses, minimum scores, graduation years, institutions) and the pipeline (the company's hiring test, screening interview plan, HR interview; locked once people apply). Per job: applicants with bulk shortlist and confirmed batch reject, the AI screening ranking (read only — "nothing here changes an application"), the funnel and the screening audit log. Per applicant: the resume as sent, screening, stages, history, private notes, next stage / move / offer / place / reject.
- **Institutions** — `institution/`: their students' applications and placements with totals; `drives/`: a head proposes a placement drive to a verified company, completes or cancels it; the company admin accepts or declines, recruiters attach jobs (restricted to that institution).
- **Careers managers** — `admin/`: jobs awaiting approval (approve / send back with a note) and companies (verify / refuse / suspend / reinstate).

Pickers: courses from `catalog/common`'s `useCourseOptions`; companies and institutions from job-portal's own `/directory` (`common/api/directoryApi.ts`); hiring tests and screening plans from assessment- and ai-interview-service via `employer/api/stagePickersApi.ts`. The resume snapshot has its own small renderer (`employer/components/applicant/ResumeSnapshot.tsx`) rather than importing career's.

**Backend change for this module (job-portal-service):** `GET /directory/companies` and `GET /directory/institutions` — user-management lets a member list only their own organisation, so a recruiter couldn't find an institution to restrict a job to and a head couldn't find a company to invite to a drive. Tested; docs and OpenAPI updated.

**Screens (2026-10-19 redesign):** students get the job list beside the chosen job, applied to in place (`board/components/JobPanel` + `ApplyBox`: resumes best ATS score first), and "My applications" as cards showing each job's steps and the one thing to do next — both computed by job-portal-service (`steps`, `progress`, `next_action`; the page only maps an action kind to where it is done). The super admin's applicants tab has the job's own stage tabs (`funnel.stages`, filtered by their statuses), the AI ranking as a banner whose button only *selects* its shortlist, and a bulk bar where a person shortlists or rejects.

**Not built:** an edited job shows a picked test/plan/institution by id until it is re-picked (the job stores ids only; course names are resolved).
