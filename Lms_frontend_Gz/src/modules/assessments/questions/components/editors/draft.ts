import { newOptionId } from "@/modules/assessments/questions/lib/ids";
import type {
  ChoiceOption,
  FillInBlank,
  MatchItem,
  RubricCriterion,
  ScoringMode,
} from "@/modules/assessments/questions/bodyTypes";
import type { QuestionType } from "@/modules/assessments/common/types";

/**
 * One state shape holding every question type's editable fields at once — the active type's
 * fields are used, the rest just sit idle. Simpler than ten separate form states for something
 * that's edited as a single unit and serialized to `body`/`answer_key` only on save.
 */
export interface QuestionDraft {
  options: ChoiceOption[];
  correct: string[];
  scoring: ScoringMode;
  boolCorrect: boolean;
  blanks: FillInBlank[];
  left: MatchItem[];
  right: MatchItem[];
  pairs: Record<string, string>;
  orderItems: MatchItem[];
  problemId: string;
  languages: string;
  rubric: RubricCriterion[];
  maxWords: string;
  modelAnswer: string;
  allowedExtensions: string;
  maxFiles: string;
  maxSizeMb: string;
}

export function emptyDraft(): QuestionDraft {
  const a = newOptionId();
  const b = newOptionId();
  return {
    options: [{ id: a, text: "" }, { id: b, text: "" }],
    correct: [],
    scoring: "all_or_nothing",
    boolCorrect: true,
    blanks: [{ answers: [] }],
    left: [{ id: newOptionId(), text: "" }, { id: newOptionId(), text: "" }],
    right: [{ id: newOptionId(), text: "" }, { id: newOptionId(), text: "" }],
    pairs: {},
    orderItems: [{ id: newOptionId(), text: "" }, { id: newOptionId(), text: "" }],
    problemId: "",
    languages: "",
    rubric: [],
    maxWords: "",
    modelAnswer: "",
    allowedExtensions: "",
    maxFiles: "1",
    maxSizeMb: "10",
  };
}

/** Rehydrates a draft from an existing question's real body/answer_key (edit mode). */
export function draftFromQuestion(type: QuestionType, body: Record<string, unknown>, answerKey: Record<string, unknown>): QuestionDraft {
  const draft = emptyDraft();
  switch (type) {
    case "mcq_single":
      draft.options = (body.options as ChoiceOption[]) ?? draft.options;
      draft.correct = answerKey.correct ? [answerKey.correct as string] : [];
      return draft;
    case "mcq_multi":
      draft.options = (body.options as ChoiceOption[]) ?? draft.options;
      draft.correct = (answerKey.correct as string[]) ?? [];
      draft.scoring = (answerKey.scoring as ScoringMode) ?? draft.scoring;
      return draft;
    case "true_false":
      draft.boolCorrect = (answerKey.correct as boolean) ?? true;
      return draft;
    case "fill_in":
      draft.blanks = (answerKey.blanks as FillInBlank[]) ?? draft.blanks;
      draft.scoring = (answerKey.scoring as ScoringMode) ?? draft.scoring;
      return draft;
    case "match":
      draft.left = (body.left as MatchItem[]) ?? draft.left;
      draft.right = (body.right as MatchItem[]) ?? draft.right;
      draft.pairs = (answerKey.pairs as Record<string, string>) ?? draft.pairs;
      draft.scoring = (answerKey.scoring as ScoringMode) ?? draft.scoring;
      return draft;
    case "ordering":
      draft.orderItems = (body.items as MatchItem[]) ?? draft.orderItems;
      return draft;
    case "coding":
    case "sql":
      draft.problemId = (body.problem_id as string) ?? "";
      draft.languages = ((body.languages as string[]) ?? []).join(", ");
      draft.scoring = (answerKey.scoring as ScoringMode) ?? draft.scoring;
      return draft;
    case "subjective":
      draft.rubric = (body.rubric as RubricCriterion[]) ?? [];
      draft.maxWords = body.max_words ? String(body.max_words) : "";
      draft.modelAnswer = (answerKey.model_answer as string) ?? "";
      return draft;
    case "file_submission":
      draft.allowedExtensions = ((body.allowed_extensions as string[]) ?? []).join(", ");
      draft.maxFiles = body.max_files ? String(body.max_files) : "1";
      draft.maxSizeMb = body.max_size_mb ? String(body.max_size_mb) : "10";
      draft.rubric = (body.rubric as RubricCriterion[]) ?? [];
      return draft;
    default:
      return draft;
  }
}

/** Serializes the active type's fields back to the real `body`/`answer_key` shapes. */
export function draftToBodyAndAnswerKey(type: QuestionType, draft: QuestionDraft): { body: Record<string, unknown>; answer_key: Record<string, unknown> } {
  switch (type) {
    case "mcq_single":
      return { body: { options: draft.options }, answer_key: { correct: draft.correct[0] ?? "" } };
    case "mcq_multi":
      return { body: { options: draft.options }, answer_key: { correct: draft.correct, scoring: draft.scoring } };
    case "true_false":
      return { body: {}, answer_key: { correct: draft.boolCorrect } };
    case "fill_in":
      return { body: { blanks: draft.blanks.length }, answer_key: { blanks: draft.blanks, scoring: draft.scoring } };
    case "match":
      return { body: { left: draft.left, right: draft.right }, answer_key: { pairs: draft.pairs, scoring: draft.scoring } };
    case "ordering":
      return { body: { items: draft.orderItems }, answer_key: { order: draft.orderItems.map((item) => item.id), scoring: "all_or_nothing" } };
    case "coding":
    case "sql": {
      const languages = draft.languages.split(",").map((value) => value.trim()).filter(Boolean);
      return { body: { problem_id: draft.problemId, ...(languages.length ? { languages } : {}) }, answer_key: { scoring: draft.scoring } };
    }
    case "subjective":
      return {
        body: { ...(draft.rubric.length ? { rubric: draft.rubric } : {}), ...(draft.maxWords ? { max_words: Number(draft.maxWords) } : {}) },
        answer_key: draft.modelAnswer ? { model_answer: draft.modelAnswer } : {},
      };
    case "file_submission": {
      const extensions = draft.allowedExtensions.split(",").map((value) => value.trim()).filter(Boolean);
      return {
        body: {
          ...(extensions.length ? { allowed_extensions: extensions } : {}),
          max_files: Number(draft.maxFiles),
          max_size_mb: Number(draft.maxSizeMb),
          ...(draft.rubric.length ? { rubric: draft.rubric } : {}),
        },
        answer_key: {},
      };
    }
    default:
      return { body: {}, answer_key: {} };
  }
}
