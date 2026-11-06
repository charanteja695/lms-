import type { Suggestion } from "@/modules/career/resumes/api/resumeToolsApi";
import { Alert, Button } from "@/shared/ui";

/**
 * AI suggestions with career-service's own checks shown: a suggestion that mentions a number, link, name or keyword
 * that isn't in the student's facts is marked and cannot be applied.
 */
export function SuggestionList({ suggestions, onApply }: { suggestions: Suggestion[]; onApply: (text: string, index: number) => void }) {
  return (
    <ul className="space-y-2">
      {suggestions.map((suggestion, index) => (
        <li key={index} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          {suggestion.original && <p className="mb-1 text-xs text-slate-400 line-through">{suggestion.original}</p>}
          <p className="text-slate-800">{suggestion.text}</p>
          {suggestion.metric_prompt && <p className="mt-1 text-xs text-amber-700">{suggestion.metric_prompt}</p>}
          {!suggestion.applicable && (
            <Alert tone="warning" className="mt-2">
              Mentions something not in your profile ({suggestion.warnings.map((w) => `${w.type}: ${w.value}`).join(", ")}). Not applied — add it to your profile first if it's true.
            </Alert>
          )}
          {suggestion.applicable && (
            <Button size="sm" variant="secondary" className="mt-2" onClick={() => onApply(suggestion.text, index)}>
              Use this
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}
