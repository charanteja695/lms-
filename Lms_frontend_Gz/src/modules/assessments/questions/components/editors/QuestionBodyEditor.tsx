import { ChoiceEditor } from "@/modules/assessments/questions/components/editors/ChoiceEditor";
import { CodingEditor } from "@/modules/assessments/questions/components/editors/CodingEditor";
import type { QuestionDraft } from "@/modules/assessments/questions/components/editors/draft";
import { FileSubmissionEditor } from "@/modules/assessments/questions/components/editors/FileSubmissionEditor";
import { FillInEditor } from "@/modules/assessments/questions/components/editors/FillInEditor";
import { MatchEditor } from "@/modules/assessments/questions/components/editors/MatchEditor";
import { OrderingEditor } from "@/modules/assessments/questions/components/editors/OrderingEditor";
import { SubjectiveEditor } from "@/modules/assessments/questions/components/editors/SubjectiveEditor";
import { TrueFalseEditor } from "@/modules/assessments/questions/components/editors/TrueFalseEditor";
import type { QuestionType } from "@/modules/assessments/common/types";

/** Dispatches to the right body/answer_key editor for the question's type. */
export function QuestionBodyEditor({ type, draft, onChange }: { type: QuestionType; draft: QuestionDraft; onChange: (draft: QuestionDraft) => void }) {
  const set = (patch: Partial<QuestionDraft>) => onChange({ ...draft, ...patch });

  switch (type) {
    case "mcq_single":
      return <ChoiceEditor multi={false} options={draft.options} correct={draft.correct} scoring={draft.scoring} onOptionsChange={(options) => set({ options })} onCorrectChange={(correct) => set({ correct })} onScoringChange={(scoring) => set({ scoring })} />;
    case "mcq_multi":
      return <ChoiceEditor multi options={draft.options} correct={draft.correct} scoring={draft.scoring} onOptionsChange={(options) => set({ options })} onCorrectChange={(correct) => set({ correct })} onScoringChange={(scoring) => set({ scoring })} />;
    case "true_false":
      return <TrueFalseEditor correct={draft.boolCorrect} onChange={(boolCorrect) => set({ boolCorrect })} />;
    case "fill_in":
      return <FillInEditor blanks={draft.blanks} scoring={draft.scoring} onBlanksChange={(blanks) => set({ blanks })} onScoringChange={(scoring) => set({ scoring })} />;
    case "match":
      return (
        <MatchEditor
          left={draft.left}
          right={draft.right}
          pairs={draft.pairs}
          scoring={draft.scoring}
          onLeftChange={(left) => set({ left })}
          onRightChange={(right) => set({ right })}
          onPairsChange={(pairs) => set({ pairs })}
          onScoringChange={(scoring) => set({ scoring })}
        />
      );
    case "ordering":
      return <OrderingEditor items={draft.orderItems} onChange={(orderItems) => set({ orderItems })} />;
    case "coding":
    case "sql":
      return (
        <CodingEditor
          problemId={draft.problemId}
          languages={draft.languages}
          scoring={draft.scoring}
          onProblemIdChange={(problemId) => set({ problemId })}
          onLanguagesChange={(languages) => set({ languages })}
          onScoringChange={(scoring) => set({ scoring })}
        />
      );
    case "subjective":
      return (
        <SubjectiveEditor
          rubric={draft.rubric}
          maxWords={draft.maxWords}
          modelAnswer={draft.modelAnswer}
          onRubricChange={(rubric) => set({ rubric })}
          onMaxWordsChange={(maxWords) => set({ maxWords })}
          onModelAnswerChange={(modelAnswer) => set({ modelAnswer })}
        />
      );
    case "file_submission":
      return (
        <FileSubmissionEditor
          allowedExtensions={draft.allowedExtensions}
          maxFiles={draft.maxFiles}
          maxSizeMb={draft.maxSizeMb}
          rubric={draft.rubric}
          onAllowedExtensionsChange={(allowedExtensions) => set({ allowedExtensions })}
          onMaxFilesChange={(maxFiles) => set({ maxFiles })}
          onMaxSizeMbChange={(maxSizeMb) => set({ maxSizeMb })}
          onRubricChange={(rubric) => set({ rubric })}
        />
      );
    default:
      return null;
  }
}
