import { describe, expect, it } from "vitest";

import { emptyJobForm, toJobBody } from "./jobForm";

describe("job form mapping", () => {
  it("converts lakhs, years, lists and picks to the API body", () => {
    const body = toJobBody({
      ...emptyJobForm(), title: " Backend dev ", description: "APIs", locations: "Chennai, Pune", experience_min_years: "1", experience_max_years: "2.5",
      ctc_min_lakhs: "6", ctc_max_lakhs: "12.5", required_skills: "Python, SQL,", openings: "3", deadline: "2026-12-31",
      graduation_min: "2025", certificate_courses: [{ id: "11", label: "Python" }], min_scores: [{ id: "12", label: "SQL", min_percent: "70" }],
      institutions: [{ id: "21", label: "Anna" }], assessment: { id: "31", label: "Test" }, assessment_min_percent: "60", hr_interview: false,
    });
    expect(body).toMatchObject({
      title: "Backend dev", locations: ["Chennai", "Pune"], experience_min_months: 12, experience_max_months: 30, ctc_min: 600_000, ctc_max: 1_250_000,
      required_skills: ["Python", "SQL"], openings: 3, deadline_at: "2026-12-31T23:59:59Z",
      eligibility: { graduation_years: { min: 2025, max: null }, certificate_course_ids: ["11"], min_scores: [{ course_id: "12", min_percent: 70 }], institution_ids: ["21"] },
      pipeline: { assessment: { test_id: "31", min_percent: 60 }, ai_interview: null, hr_interview: false },
    });
  });

  it("leaves optional parts empty", () => {
    const body = toJobBody(emptyJobForm());
    expect(body.ctc_min).toBeNull();
    expect(body.eligibility.graduation_years).toBeNull();
    expect(body.deadline_at).toBeNull();
  });
});
