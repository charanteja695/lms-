import { CodeAnswer } from "@/modules/assessments/attempts/components/player/answers/CodeAnswer";
import { FileSubmissionAnswer } from "@/modules/assessments/attempts/components/player/answers/FileSubmissionAnswer";
import { FillInAnswer } from "@/modules/assessments/attempts/components/player/answers/FillInAnswer";
import { MatchAnswer } from "@/modules/assessments/attempts/components/player/answers/MatchAnswer";
import { McqAnswer } from "@/modules/assessments/attempts/components/player/answers/McqAnswer";
import { OrderingAnswer } from "@/modules/assessments/attempts/components/player/answers/OrderingAnswer";
import { SubjectiveAnswer } from "@/modules/assessments/attempts/components/player/answers/SubjectiveAnswer";
import { TrueFalseAnswer } from "@/modules/assessments/attempts/components/player/answers/TrueFalseAnswer";
import type { PaperQuestion } from "@/modules/assessments/attempts/paperTypes";

/** Dispatches to the right answer input for the question's type. The body shape matches docs/API.md's "Question types" table. */
export function AnswerRenderer({ attemptId, question, response, onChange, disabled }: {
  attemptId: string;
  question: PaperQuestion;
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const body = question.body;
  switch (question.question_type) {
    case "mcq_single":
      return <McqAnswer multi={false} options={(body.options as { id: string; text: string }[]) ?? []} response={response} onChange={onChange} disabled={disabled} />;
    case "mcq_multi":
      return <McqAnswer multi options={(body.options as { id: string; text: string }[]) ?? []} response={response} onChange={onChange} disabled={disabled} />;
    case "true_false":
      return <TrueFalseAnswer response={response} onChange={onChange} disabled={disabled} />;
    case "fill_in":
      return <FillInAnswer blanks={(body.blanks as number) ?? 1} response={response} onChange={onChange} disabled={disabled} />;
    case "match":
      return <MatchAnswer left={(body.left as { id: string; text: string }[]) ?? []} right={(body.right as { id: string; text: string }[]) ?? []} response={response} onChange={onChange} disabled={disabled} />;
    case "ordering":
      return <OrderingAnswer items={(body.items as { id: string; text: string }[]) ?? []} response={response} onChange={onChange} disabled={disabled} />;
    case "coding":
      return <CodeAnswer isSql={false} allowedLanguages={body.languages as string[] | undefined} response={response} onChange={onChange} disabled={disabled} />;
    case "sql":
      return <CodeAnswer isSql response={response} onChange={onChange} disabled={disabled} />;
    case "subjective":
      return <SubjectiveAnswer maxWords={body.max_words as number | undefined} response={response} onChange={onChange} disabled={disabled} />;
    case "file_submission":
      return (
        <FileSubmissionAnswer
          attemptId={attemptId}
          questionId={question.question_id}
          allowedExtensions={body.allowed_extensions as string[] | undefined}
          maxFiles={(body.max_files as number) ?? 1}
          maxSizeMb={(body.max_size_mb as number) ?? 10}
          response={response}
          onChange={onChange}
          disabled={disabled}
        />
      );
    default:
      return null;
  }
}
