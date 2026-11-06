# AI Interview module

> Status: **Done** · Backend: `lms-backend/ai-interview-service` · Roadmap: Phase 10
> Gated by the single `ai_interview` section (students; employer admins/recruiters; `careers.manage`).

One nav item. `common/pages/InterviewHomePage` sends students to practice, employers to screening and careers managers to plans (`common/hooks/useInterviewRights` mirrors the service's `policy.py`).

- **Students**, in `student/`:
  - **Practice page:** their interviews (practice and screening invites) plus the published practice plans.
  - **Interview room:**
    - consent step, then the start;
    - the server-owned clock (`ends_at`, `/time-left`) and the current round;
    - text answers, or voice (recorded, sent to `/turns/audio`, optional spoken questions);
    - a live coding panel in the languages the current round allows (code runs on the server);
    - the end. Every answer carries an `Idempotency-Key`.
  - **Report:** scores, strengths, what to work on and an improvement plan (shown only once released); an appeal, or a retake once one is granted.
- **Plans**, in `plans/`. Employers write screening plans; careers managers write practice plans.
  - **Editing:** a draft can be edited (rounds editor with core questions, languages and criteria), then published, retired or forked into a new version.
  - **Published screening plans** add two cards:
    - Calibration: the AI is scored against human-rated samples.
    - Fairness audit: advance rates by group.
- **Screening**, in `screening/`:
  - **Company interviews:** the list of the company's screening interviews.
  - **Interview page:** the transcript, and the AI evaluation with the share of quoted evidence the server verified. A re-evaluate action sits on the evaluation.
  - **Reviewing:** a person confirms the recommendation or overrides it (a note is required), and chooses whether feedback is released. The candidate sees nothing until this review.
  - **Calibration samples:** a reviewed transcript can be added as a calibration sample.
  - **Appeals:** uphold or deny, by a second reviewer.

**Backend changes (ai-interview-service), tested:**
- `GET /student/interviews/{id}/transcript`, so a reload resumes the conversation.
- `InterviewOut.current_round` (type, minutes, allowed languages, number and total), so the room knows the coding languages without reading the plan.

**Student screens (2026-10-19 redesign):** set-up (`student/pages/PracticePage` + `components/PracticeSetup`): company interviews waiting on top, then role → one of the plans published for it → start, beside past interviews with their overall score; the room shows the current question large with the answer right under it and the conversation folded below; the report shows the overall score (`score_max` from the server), scores by area, round by round with the candidate's own quoted words (`components/RoundFeedback`), and "Practise again".
