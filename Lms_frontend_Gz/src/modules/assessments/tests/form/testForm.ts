import { compact, diffForUpdate } from "@/core/lib/query";
import type { ProctoringLevel, ResultVisibility, ReviewPolicy, ScoreCounting, TestKind, TimeMode } from "@/modules/assessments/common/types";
import type { Test, TestCreateBody, TestUpdateBody } from "@/modules/assessments/tests/types";

/** Form state for a test's settings (not its sections/slots — see SectionsEditor). */
export interface TestFormValues {
  title: string;
  description: string;
  instructions: string;
  kind: TestKind;
  target_id: string;
  time_mode: TimeMode;
  duration_minutes: string;
  pass_mark_percent: string;
  max_attempts: string;
  cooldown_hours: string;
  score_counting: ScoreCounting;
  negative_marking_percent: string;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  result_visibility: ResultVisibility;
  review_policy: ReviewPolicy;
  proctoring_level: ProctoringLevel;
  proctoring_screen_share: boolean;
  requires_schedule: boolean;
}

export function emptyTestForm(preset: Partial<TestFormValues> = {}): TestFormValues {
  return {
    title: "",
    description: "",
    instructions: "",
    kind: "practice",
    target_id: "",
    time_mode: "overall",
    duration_minutes: "60",
    pass_mark_percent: "60",
    max_attempts: "0",
    cooldown_hours: "0",
    score_counting: "highest",
    negative_marking_percent: "0",
    shuffle_questions: true,
    shuffle_options: true,
    result_visibility: "immediate",
    review_policy: "none",
    proctoring_level: "none",
    proctoring_screen_share: false,
    requires_schedule: false,
    ...preset,
  };
}

export function testToForm(test: Test): TestFormValues {
  return {
    title: test.title,
    description: test.description ?? "",
    instructions: test.instructions ?? "",
    kind: test.kind,
    target_id: test.target_id ?? "",
    time_mode: test.time_mode,
    duration_minutes: test.duration_minutes ? String(test.duration_minutes) : "",
    pass_mark_percent: String(test.pass_mark_percent),
    max_attempts: String(test.max_attempts),
    cooldown_hours: String(test.cooldown_hours),
    score_counting: test.score_counting,
    negative_marking_percent: String(test.negative_marking_percent),
    shuffle_questions: test.shuffle_questions,
    shuffle_options: test.shuffle_options,
    result_visibility: test.result_visibility,
    review_policy: test.review_policy,
    proctoring_level: test.proctoring_level,
    proctoring_screen_share: test.proctoring_screen_share,
    requires_schedule: test.requires_schedule,
  };
}

function shape(values: TestFormValues) {
  return {
    title: values.title,
    description: values.description || null,
    instructions: values.instructions || null,
    time_mode: values.time_mode,
    duration_minutes: values.time_mode === "overall" && values.duration_minutes ? Number(values.duration_minutes) : null,
    pass_mark_percent: Number(values.pass_mark_percent),
    max_attempts: Number(values.max_attempts),
    cooldown_hours: Number(values.cooldown_hours),
    score_counting: values.score_counting,
    negative_marking_percent: Number(values.negative_marking_percent),
    shuffle_questions: values.shuffle_questions,
    shuffle_options: values.shuffle_options,
    result_visibility: values.result_visibility,
    review_policy: values.review_policy,
    proctoring_level: values.proctoring_level,
    proctoring_screen_share: values.proctoring_level === "strict" && values.proctoring_screen_share,
    requires_schedule: values.requires_schedule,
  };
}

export function toTestCreateBody(values: TestFormValues): TestCreateBody {
  return compact({ ...shape(values), kind: values.kind, target_id: values.target_id || undefined }) as TestCreateBody;
}

export function toTestUpdateBody(initial: TestFormValues, values: TestFormValues): TestUpdateBody {
  const body = (diffForUpdate(shape(initial), shape(values)) ?? {}) as Record<string, unknown>;
  if (values.kind !== initial.kind) body.kind = values.kind;
  if (values.target_id !== initial.target_id) body.target_id = values.target_id || null;
  return body as TestUpdateBody;
}

export function isTestField(field: string): boolean {
  return /^(title|description|instructions|kind|target_id|time_mode|duration_minutes|pass_mark_percent|max_attempts|cooldown_hours|score_counting|negative_marking_percent|shuffle_questions|shuffle_options|result_visibility|review_policy|proctoring_level|proctoring_screen_share|requires_schedule)$/.test(field);
}
