import { useEffect, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { AskTutorButton } from "@/modules/code-execution/common/components/AskTutorButton";
import { LanguageSelect } from "@/modules/code-execution/languages/components/LanguageSelect";
import { useGetSavedCodeQuery, useSaveCodeMutation } from "@/modules/code-execution/problems/api/problemsApi";
import { useSubmissionExecution } from "@/modules/code-execution/problems/hooks/useSubmissionExecution";
import type { Problem } from "@/modules/code-execution/problems/types";
import { useRunExecution } from "@/modules/code-execution/runs/hooks/useRunExecution";
import { RunOutputPanel } from "@/modules/code-execution/runs/components/RunOutputPanel";
import { SubmissionResultPanel } from "@/modules/code-execution/submissions/components/SubmissionResultPanel";
import { Button, Card, CodeEditor, Tabs, Textarea } from "@/shared/ui";

export function ProblemWorkspace({ problem }: { problem: Problem }) {
  const notify = useNotify();
  const [language, setLanguage] = useState(problem.allowed_languages[0] ?? "");
  const [source, setSource] = useState("");
  const [stdin, setStdin] = useState("");
  const [tab, setTab] = useState<"run" | "submit">("run");
  const { data: savedCode } = useGetSavedCodeQuery({ problemId: problem.problem_id, language }, { skip: !language });
  const [saveCode, { isLoading: saving }] = useSaveCodeMutation();
  const { run, isExecuting, execute } = useRunExecution();
  const { submission, isSubmitting, submit } = useSubmissionExecution(problem.problem_id);

  useEffect(() => {
    if (savedCode) setSource(savedCode.source);
  }, [savedCode]);

  return (
    <Card
      title="Workspace"
      actions={
        <LanguageSelect
          value={language}
          onChange={setLanguage}
          allowed={problem.allowed_languages.length > 0 ? problem.allowed_languages : undefined}
        />
      }
    >
      <div className="space-y-4">
        <CodeEditor value={source} onChange={setSource} rows={16} />
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            loading={saving}
            disabled={!language}
            onClick={async () => {
              try {
                await saveCode({ problemId: problem.problem_id, language, source }).unwrap();
                notify.success("Draft saved");
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Save draft
          </Button>
          <AskTutorButton code={source} language={language} title={problem.title} />
          <Button
            variant="secondary"
            icon="play"
            loading={isExecuting}
            disabled={!language}
            onClick={() => {
              setTab("run");
              void execute({ language, source, stdin, problem_id: problem.problem_type === "sql" ? problem.problem_id : undefined });
            }}
          >
            Run
          </Button>
          <Button
            icon="upload"
            loading={isSubmitting}
            disabled={!language}
            onClick={() => {
              setTab("submit");
              void submit(language, source);
            }}
          >
            Submit
          </Button>
        </div>

        <Tabs
          tabs={[
            { value: "run", label: "Run" },
            { value: "submit", label: "Submissions" },
          ]}
          value={tab}
          onChange={setTab}
        />
        {tab === "run" ? (
          <div className="space-y-3">
            <Card title="stdin">
              <Textarea value={stdin} onChange={(event) => setStdin(event.target.value)} rows={4} placeholder="Input passed to your program" />
            </Card>
            <RunOutputPanel run={run} isExecuting={isExecuting} />
          </div>
        ) : (
          <SubmissionResultPanel submission={submission} isSubmitting={isSubmitting} />
        )}
      </div>
    </Card>
  );
}
