import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useDeleteTestCaseMutation, useListTestCasesQuery, useReorderTestCasesMutation } from "@/modules/code-execution/problems/api/problemsApi";
import { TestCaseFormDialog } from "@/modules/code-execution/problems/components/detail/TestCaseFormDialog";
import { TestCaseImportDialog } from "@/modules/code-execution/problems/components/detail/TestCaseImportDialog";
import { Badge, Button, Card, ConfirmDialog, EmptyState, Icon } from "@/shared/ui";

export function TestCasesCard({ problemId, editable }: { problemId: string; editable: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: testCases, isFetching } = useListTestCasesQuery(problemId);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [deleteTestCase] = useDeleteTestCaseMutation();
  const [reorder] = useReorderTestCasesMutation();
  const sorted = [...(testCases ?? [])].sort((a, b) => a.position - b.position);

  const move = async (index: number, direction: "up" | "down") => {
    const next = [...sorted];
    const swapWith = direction === "up" ? index - 1 : index + 1;
    [next[index], next[swapWith]] = [next[swapWith]!, next[index]!];
    try {
      await reorder({ problemId, testCaseIds: next.map((item) => item.test_case_id) }).unwrap();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card title="Test cases" description="Hidden cases are never sent to a client." actions={editable && <><Button size="sm" variant="secondary" icon="upload" onClick={() => setImporting(true)}>Import</Button><Button size="sm" icon="plus" onClick={() => setAdding(true)}>Test case</Button></>}>
      {!isFetching && sorted.length === 0 ? (
        <EmptyState icon="terminal" title="No test cases yet" description="Add test cases (or import a file) so submissions can be judged." />
      ) : (
        <div className="space-y-2">
          {sorted.map((testCase, index) => (
            <div key={testCase.test_case_id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <span className="w-6 text-center text-sm font-medium text-slate-400">{testCase.position}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-slate-800">{testCase.explanation || `Test case ${testCase.position}`}</p>
                <p className="text-xs text-slate-500">
                  Weight {testCase.weight}
                  {testCase.compare_mode && ` · ${testCase.compare_mode}`}
                </p>
              </div>
              {testCase.is_sample && <Badge tone="blue">Sample</Badge>}
              {editable && (
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" aria-label="Move up" disabled={index === 0} onClick={() => void move(index, "up")}>
                    <Icon name="arrowUp" size={14} />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="Move down" disabled={index === sorted.length - 1} onClick={() => void move(index, "down")}>
                    <Icon name="arrowDown" size={14} />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="Edit test case" onClick={() => setEditing(testCase.test_case_id)}>
                    <Icon name="edit" size={14} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Delete test case"
                    onClick={() =>
                      confirm.ask({ title: "Delete this test case?", description: "This cannot be undone.", confirmLabel: "Delete" }, async () => {
                        try {
                          await deleteTestCase({ problemId, testCaseId: testCase.test_case_id }).unwrap();
                          notify.success("Test case deleted");
                        } catch (error) {
                          notify.apiError(error);
                        }
                      })
                    }
                  >
                    <Icon name="trash" size={14} />
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {adding && <TestCaseFormDialog open={adding} onClose={() => setAdding(false)} problemId={problemId} />}
      {importing && <TestCaseImportDialog problemId={problemId} onClose={() => setImporting(false)} />}
      {editing && <TestCaseFormDialog open={Boolean(editing)} onClose={() => setEditing(null)} problemId={problemId} testCase={sorted.find((item) => item.test_case_id === editing)} />}
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}
