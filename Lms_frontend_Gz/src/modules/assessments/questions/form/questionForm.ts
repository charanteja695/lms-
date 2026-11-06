import { compact, diffForUpdate } from "@/core/lib/query";
import type { Bloom, QuestionType } from "@/modules/assessments/common/types";
import { draftFromQuestion, draftToBodyAndAnswerKey, emptyDraft, type QuestionDraft } from "@/modules/assessments/questions/components/editors/draft";
import type { Question, QuestionCreateBody, QuestionUpdateBody } from "@/modules/assessments/questions/types";

/** Form state for the fields every question type shares. Type-specific body/answer_key live in a separate QuestionDraft (see components/editors/draft.ts). */
export interface QuestionFormValues {
  question_type: QuestionType;
  text: string;
  explanation: string;
  default_marks: string;
  difficulty: string;
  bloom: string;
  skills: string;
  topics: string;
  tags: string;
}

export function emptyQuestionForm(): QuestionFormValues {
  return { question_type: "mcq_single", text: "", explanation: "", default_marks: "1", difficulty: "3", bloom: "", skills: "", topics: "", tags: "" };
}

function toList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function questionToForm(question: Question): { values: QuestionFormValues; draft: QuestionDraft } {
  const version = question.working ?? question.current;
  if (!version) return { values: emptyQuestionForm(), draft: emptyDraft() };
  const values: QuestionFormValues = {
    question_type: question.question_type,
    text: version.text,
    explanation: version.explanation ?? "",
    default_marks: String(version.default_marks),
    difficulty: String(version.difficulty),
    bloom: version.bloom ?? "",
    skills: version.skills.join(", "),
    topics: version.topics.join(", "),
    tags: version.tags.join(", "),
  };
  return { values, draft: draftFromQuestion(question.question_type, version.body, version.answer_key) };
}

function shape(values: QuestionFormValues) {
  return {
    text: values.text,
    explanation: values.explanation,
    default_marks: Number(values.default_marks),
    difficulty: Number(values.difficulty),
    bloom: values.bloom || undefined,
    skills: toList(values.skills),
    topics: toList(values.topics),
    tags: toList(values.tags),
  };
}

export function toQuestionCreateBody(values: QuestionFormValues, draft: QuestionDraft): QuestionCreateBody {
  const { body, answer_key } = draftToBodyAndAnswerKey(values.question_type, draft);
  return compact({ ...shape(values), question_type: values.question_type, body, answer_key, bloom: (values.bloom || null) as Bloom | null }) as QuestionCreateBody;
}

export function toQuestionUpdateBody(initial: QuestionFormValues, values: QuestionFormValues, draft: QuestionDraft): QuestionUpdateBody {
  const before = shape(initial);
  const after = shape(values);
  const body = (diffForUpdate({ ...before, skills: undefined, topics: undefined, tags: undefined }, { ...after, skills: undefined, topics: undefined, tags: undefined }) ?? {}) as Record<string, unknown>;
  if (JSON.stringify(before.skills) !== JSON.stringify(after.skills)) body.skills = after.skills;
  if (JSON.stringify(before.topics) !== JSON.stringify(after.topics)) body.topics = after.topics;
  if (JSON.stringify(before.tags) !== JSON.stringify(after.tags)) body.tags = after.tags;
  // The type-specific editor is always shown, so always resend body/answer_key — simpler and safe (idempotent) than diffing nested structures.
  const { body: bodyValue, answer_key } = draftToBodyAndAnswerKey(values.question_type, draft);
  body.body = bodyValue;
  body.answer_key = answer_key;
  return body as QuestionUpdateBody;
}

export function isQuestionField(field: string): boolean {
  return /^(text|explanation|default_marks|difficulty|bloom|skills|topics|tags|body|answer_key)$/.test(field);
}
