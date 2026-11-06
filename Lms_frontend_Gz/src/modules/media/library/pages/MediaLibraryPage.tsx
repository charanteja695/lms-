import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useListParams } from "@/core/hooks/useListParams";
import { useNotify } from "@/core/hooks/useNotify";
import { useArchiveMediaMutation, useListMediaQuery, useRestoreMediaMutation } from "@/modules/media/api/mediaApi";
import { KIND_LABELS, STATUS_LABELS } from "@/modules/media/labels";
import { MediaPreviewModal } from "@/modules/media/library/components/MediaPreviewModal";
import { MediaSummaryTiles } from "@/modules/media/library/components/MediaSummaryTiles";
import { useMediaColumns } from "@/modules/media/library/components/useMediaColumns";
import type { MediaAsset, MediaFilters, MediaKind, MediaStatus } from "@/modules/media/types";
import { Button, Card, ConfirmDialog, DataTable, EmptyState, FilterBar, FilterSelect, PageHeader, Pagination } from "@/shared/ui";

const KINDS = (["video", "document"] as const).map((value) => ({ value, label: KIND_LABELS[value] }));
const STATUSES = (["ready", "processing", "failed"] as const).map((value) => ({ value, label: STATUS_LABELS[value] }));
const SHOWING = [{ value: "live", label: "In use" }, { value: "archived", label: "Archived" }];

/** Every lesson video and PDF in one place: find a file, preview it, archive what is no longer needed. */
export function MediaLibraryPage() {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { params, update, reset } = useListParams<{ kind: string; status: string; search: string; archived: boolean }>({ page: 1, per_page: 20 });
  const filters = params as MediaFilters;
  const { data, isFetching, isError, refetch } = useListMediaQuery(filters);
  const [archive] = useArchiveMediaMutation();
  const [restore] = useRestoreMediaMutation();
  const [preview, setPreview] = useState<MediaAsset | null>(null);
  const activeCount = [filters.kind, filters.status, filters.search, filters.archived].filter(Boolean).length;

  const columns = useMediaColumns({
    onPreview: setPreview,
    onArchive: (asset) =>
      confirm.ask(
        { title: `Archive ${asset.original_filename}?`, description: "Learners can no longer open it. Lessons that use it show it as unavailable until you restore it.", confirmLabel: "Archive" },
        async () => { await archive(asset.asset_id).unwrap().then(() => notify.success("File archived"), notify.apiError); },
      ),
    onRestore: (asset) => void restore(asset.asset_id).unwrap().then(() => notify.success("File restored"), notify.apiError),
  });
  const assets = data?.assets ?? [];

  return (
    <>
      <PageHeader title="Videos & PDFs" description="Every lesson video and PDF. Upload files from a lesson in the course builder; manage them here." />
      <MediaSummaryTiles />
      <Card bodyClassName="p-0">
        <FilterBar
          search={filters.search ?? ""}
          onSearch={(search) => update({ search })}
          searchPlaceholder="Search by file name"
          activeCount={activeCount}
          onReset={reset}
          primary={
            <>
              <FilterSelect label="Type" value={filters.kind} options={KINDS} onChange={(kind) => update({ kind: kind as MediaKind | undefined })} />
              <FilterSelect label="Status" value={filters.status} options={STATUSES} onChange={(status) => update({ status: status as MediaStatus | undefined })} />
              <FilterSelect label="Showing" placeholder="In use" value={filters.archived ? "archived" : undefined} options={SHOWING} onChange={(v) => update({ archived: v === "archived" ? true : undefined })} />
            </>
          }
        />
        {isError ? (
          <EmptyState icon="alert" title="Could not load files" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <DataTable
            columns={columns}
            rows={assets}
            rowKey={(a) => a.asset_id}
            loading={isFetching}
            empty={
              <EmptyState
                icon={filters.kind === "video" ? "video" : "fileText"}
                title={activeCount ? "No files match" : "No videos or PDFs yet"}
                description={activeCount ? "Try another search or clear the filters." : "Add a video or PDF lesson in the course builder and it appears here."}
                action={activeCount ? <Button variant="secondary" onClick={reset}>Clear filters</Button> : undefined}
              />
            }
          />
        )}
        <div className="border-t border-slate-100 px-5 py-3">
          <Pagination pageContext={data?.page_context} disabled={isFetching} onPageChange={(page) => update({ page })} onPerPageChange={(per_page) => update({ per_page })} />
        </div>
      </Card>
      <MediaPreviewModal asset={preview} onClose={() => setPreview(null)} />
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
