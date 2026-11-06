import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useGrammarCheckMutation, type GrammarIssue } from "@/modules/career/resumes/api/resumeToolsApi";
import { Badge, Button } from "@/shared/ui";

/** Rule-based checks of the summary and the student's own bullets (saved draft). */
export function GrammarPanel({ resumeId }: { resumeId: string }) {
  const notify = useNotify();
  const [check, { isLoading }] = useGrammarCheckMutation();
  const [issues, setIssues] = useState<GrammarIssue[] | null>(null);

  return (
    <div className="space-y-3">
      <Button
        size="sm"
        variant="secondary"
        loading={isLoading}
        onClick={async () => {
          try {
            setIssues(await check(resumeId).unwrap());
          } catch (error) {
            notify.apiError(error);
          }
        }}
      >
        Check writing
      </Button>
      {issues?.length === 0 && <p className="text-sm text-brand-700">No issues found.</p>}
      {issues && issues.length > 0 && (
        <ul className="space-y-2 text-sm">
          {issues.map((issue, index) => (
            <li key={index} className="rounded border border-slate-100 p-2">
              <p className="flex items-center gap-2">
                <Badge tone={issue.severity === "error" ? "red" : "amber"}>{issue.where}</Badge>
                <span className="text-slate-700">{issue.message}</span>
              </p>
              {issue.excerpt && <p className="mt-1 text-xs text-slate-500">“{issue.excerpt}”</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
