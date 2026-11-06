/**
 * Per-question-type shapes of `body` (what the student sees) and `answer_key` (what's correct —
 * never sent to a student before results). Mirrors assessment-service's docs/API.md "Question types"
 * table exactly; the API itself types both as a generic object, so these are narrowed by the
 * question's own `question_type` wherever they're used.
 */
export type ScoringMode = "all_or_nothing" | "partial";

export interface ChoiceOption {
  id: string;
  text: string;
}

export interface McqSingleBody {
  options: ChoiceOption[];
}
export interface McqSingleAnswerKey {
  correct: string;
}

export interface McqMultiBody {
  options: ChoiceOption[];
}
export interface McqMultiAnswerKey {
  correct: string[];
  scoring: ScoringMode;
}

export type TrueFalseBody = Record<string, never>;
export interface TrueFalseAnswerKey {
  correct: boolean;
}

export interface FillInBody {
  blanks: number;
}
export interface FillInBlank {
  answers: string[];
  case_sensitive?: boolean;
  tolerance?: number;
}
export interface FillInAnswerKey {
  blanks: FillInBlank[];
  scoring: ScoringMode;
}

export interface MatchItem {
  id: string;
  text: string;
}
export interface MatchBody {
  left: MatchItem[];
  right: MatchItem[];
}
export interface MatchAnswerKey {
  pairs: Record<string, string>;
  scoring: ScoringMode;
}

export interface OrderingBody {
  items: MatchItem[];
}
export interface OrderingAnswerKey {
  order: string[];
  scoring: ScoringMode;
}

/** coding and sql share this shape; `problem_id` refers to a code-execution-service problem. */
export interface CodingBody {
  problem_id: string;
  languages?: string[];
}
export interface CodingAnswerKey {
  scoring: ScoringMode;
}

export interface RubricCriterion {
  id: string;
  criterion: string;
  max_marks: number;
}
export interface SubjectiveBody {
  rubric?: RubricCriterion[];
  max_words?: number;
}
export interface SubjectiveAnswerKey {
  model_answer?: string;
}

export interface FileSubmissionBody {
  allowed_extensions?: string[];
  max_files: number;
  max_size_mb: number;
  rubric?: RubricCriterion[];
}
export type FileSubmissionAnswerKey = Record<string, never>;
