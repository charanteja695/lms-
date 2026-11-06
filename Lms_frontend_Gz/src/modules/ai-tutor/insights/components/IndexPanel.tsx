import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useGetIndexStatusQuery, useReindexVersionMutation } from "@/modules/ai-tutor/insights/api/insightsApi";
import type { IndexVersion } from "@/modules/ai-tutor/insights/types";
import { Badge, Button, Card, ConfirmDialog, DataTable, EmptyState, type Column } from "@/shared/ui";

function jobTone(status: string | null) {
  if (status === "failed") return "red" as const;
  if (status === "done") return "green" as const;
  return status ? ("amber" as const) : ("gray" as const);
}

/** How much of each course version the tutor can search; AI managers can embed a version again. */
export function IndexPanel({ courseId, canReindex }: { courseId: string; canReindex: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: versions = [], isFetching } = useGetIndexStatusQuery(courseId);
  const [reindex] = useReindexVersionMutation();

  const columns: Column<IndexVersion>[] = [
    { key: "version", header: "Version", render: (item) => <span className="font-mono text-xs">#{item.version_id}</span> },
    { key: "state", header: "", render: (item) => (item.retired ? <Badge tone="gray">Retired</Badge> : null) },
    { key: "chunks", header: "Embedded", render: (item) => `${item.embedded_chunks} / ${item.chunks}` },
    { key: "job", header: "Job", render: (item) => <Badge tone={jobTone(item.job_status)}>{item.job_status ?? "none"}</Badge> },
    { key: "error", header: "Last error", hideOnMobile: true, render: (item) => item.last_error ?? "—" },
    {
      key: "actions",
      header: "",
      render: (item) =>
        canReindex && (
          <Button
            variant="secondary"
            size="sm"
            icon="refresh"
            onClick={() =>
              confirm.ask({ title: "Reindex this version?", description: "Its vectors are forgotten and embedded again; answers fall back to word matching meanwhile.", confirmLabel: "Reindex", tone: "primary" }, async () => {
                try {
                  await reindex(item.version_id).unwrap();
                  notify.success("Reindex queued");
                } catch (error) {
                  notify.apiError(error);
                }
              })
            }
          >
            Reindex
          </Button>
        ),
    },
  ];

  return (
    <Card title="Search index" bodyClassName="p-0">
      <DataTable columns={columns} rows={versions} rowKey={(item) => item.version_id} loading={isFetching} empty={<EmptyState icon="layers" title="Nothing indexed yet" description="A version is indexed when it's published." />} />
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}
