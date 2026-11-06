import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { CompareMode, Difficulty, ProblemStatus, ProblemType } from "@/modules/code-execution/common/types";

export interface SampleCase {
  position: number;
  input: string;
  expected: string;
  explanation: string | null;
}

/** What any signed-in user gets: a problem to read and attempt. Hidden test cases never appear here. */
export interface Problem {
  problem_id: Id;
  title: string;
  problem_type: ProblemType;
  difficulty: Difficulty;
  tags: string[];
  status: ProblemStatus;
  /** Only meaningful for the signed-in student; absent for authors/reviewers browsing generally. */
  solved?: boolean;
  attempted?: boolean;
  statement: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  allowed_languages: string[];
  samples: SampleCase[];
  created_at: IsoDateTime;
  published_at: IsoDateTime | null;
}

export interface ProblemListItem {
  problem_id: Id;
  title: string;
  problem_type: ProblemType;
  difficulty: Difficulty;
  tags: string[];
  status: ProblemStatus;
  solved?: boolean;
  attempted?: boolean;
}

/** content.author/content.review/exams.manage/super_admin: the full authoring record. */
export interface ProblemAuthor extends Problem {
  configured_languages: string[];
  compare_mode: CompareMode;
  float_tolerance: number;
  has_setup_sql: boolean;
  test_case_count: number;
  created_by: Id;
}

export interface ProblemFilters {
  status?: ProblemStatus;
  difficulty?: Difficulty;
  problem_type?: ProblemType;
  tag?: string;
  search?: string;
  solved?: boolean;
  sort_order?: SortOrder;
}

export interface ProblemCreateBody {
  title: string;
  statement: string;
  problem_type?: ProblemType;
  difficulty?: Difficulty;
  tags?: string[];
  time_limit_ms?: number;
  memory_limit_mb?: number;
  allowed_languages?: string[];
  setup_sql?: string | null;
  compare_mode?: CompareMode;
  float_tolerance?: number;
}

export interface ProblemUpdateBody {
  title?: string;
  statement?: string;
  difficulty?: Difficulty;
  tags?: string[];
  time_limit_ms?: number;
  memory_limit_mb?: number;
  allowed_languages?: string[];
  setup_sql?: string | null;
  compare_mode?: CompareMode;
  float_tolerance?: number;
}

export interface ProblemStats {
  submissions: number;
  accepted: number;
  acceptance_percent: number;
  solvers: number;
  flagged: number;
  verdicts: Record<string, number>;
}

export interface TestCase {
  test_case_id: Id;
  position: number;
  is_sample: boolean;
  input: string;
  expected: string;
  compare_mode: CompareMode | null;
  weight: number;
  explanation: string | null;
  created_at: IsoDateTime;
}

export interface TestCaseCreateBody {
  input?: string;
  expected: string;
  is_sample?: boolean;
  compare_mode?: CompareMode | null;
  weight?: number;
  explanation?: string | null;
}

export interface TestCaseUpdateBody {
  input?: string;
  expected?: string;
  is_sample?: boolean;
  compare_mode?: CompareMode | null;
  weight?: number;
  explanation?: string | null;
}

export interface SavedCode {
  problem_id: Id;
  language: string;
  source: string;
  updated_at: IsoDateTime | null;
}
