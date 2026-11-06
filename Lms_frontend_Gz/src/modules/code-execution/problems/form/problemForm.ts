import { compact, diffForUpdate } from "@/core/lib/query";
import type { CompareMode, Difficulty, ProblemType } from "@/modules/code-execution/common/types";
import type { Problem, ProblemCreateBody, ProblemUpdateBody } from "@/modules/code-execution/problems/types";

/** Form state for creating/editing a problem. Field names match the API body, except tags/allowed_languages (arrays here). */
export interface ProblemFormValues {
  title: string;
  statement: string;
  problem_type: ProblemType;
  difficulty: Difficulty;
  tags: string;
  time_limit_ms: string;
  memory_limit_mb: string;
  allowed_languages: string[];
  setup_sql: string;
  compare_mode: CompareMode;
  float_tolerance: string;
}

export function emptyProblemForm(): ProblemFormValues {
  return {
    title: "",
    statement: "",
    problem_type: "code",
    difficulty: "medium",
    tags: "",
    time_limit_ms: "2000",
    memory_limit_mb: "256",
    allowed_languages: [],
    setup_sql: "",
    compare_mode: "exact",
    float_tolerance: "0.0001",
  };
}

function toTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

export function problemToForm(problem: Problem & { compare_mode?: CompareMode; float_tolerance?: number; has_setup_sql?: boolean }): ProblemFormValues {
  return {
    title: problem.title,
    statement: problem.statement,
    problem_type: problem.problem_type,
    difficulty: problem.difficulty,
    tags: problem.tags.join(", "),
    time_limit_ms: String(problem.time_limit_ms),
    memory_limit_mb: String(problem.memory_limit_mb),
    allowed_languages: problem.allowed_languages,
    setup_sql: "",
    compare_mode: problem.compare_mode ?? "exact",
    float_tolerance: String(problem.float_tolerance ?? 0.0001),
  };
}

function shape(values: ProblemFormValues) {
  return {
    title: values.title,
    statement: values.statement,
    difficulty: values.difficulty,
    tags: toTags(values.tags),
    time_limit_ms: Number(values.time_limit_ms),
    memory_limit_mb: Number(values.memory_limit_mb),
    allowed_languages: values.allowed_languages,
    compare_mode: values.compare_mode,
    float_tolerance: Number(values.float_tolerance),
  };
}

export function toProblemCreateBody(values: ProblemFormValues): ProblemCreateBody {
  return compact({ ...shape(values), problem_type: values.problem_type, setup_sql: values.problem_type === "sql" ? values.setup_sql : undefined }) as ProblemCreateBody;
}

export function toProblemUpdateBody(initial: ProblemFormValues, values: ProblemFormValues): ProblemUpdateBody {
  const before = shape(initial);
  const after = shape(values);
  const body = (diffForUpdate({ ...before, allowed_languages: undefined, tags: undefined }, { ...after, allowed_languages: undefined, tags: undefined }) ?? {}) as Record<string, unknown>;
  if (JSON.stringify(before.allowed_languages) !== JSON.stringify(after.allowed_languages)) body.allowed_languages = after.allowed_languages;
  if (JSON.stringify(before.tags) !== JSON.stringify(after.tags)) body.tags = after.tags;
  if (values.setup_sql) body.setup_sql = values.setup_sql;
  return body as ProblemUpdateBody;
}

export function isProblemField(field: string): boolean {
  return /^(title|statement|difficulty|tags|time_limit_ms|memory_limit_mb|allowed_languages|setup_sql|compare_mode|float_tolerance)$/.test(field);
}
