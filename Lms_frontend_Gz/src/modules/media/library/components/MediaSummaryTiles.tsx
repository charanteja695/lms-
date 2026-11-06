import { formatBytes } from "@/core/lib/format";
import { useGetMediaSummaryQuery } from "@/modules/media/api/mediaApi";
import { StatTile } from "@/shared/ui";

/** Videos and PDFs in use (with their size), files that failed to process, and archived files. */
export function MediaSummaryTiles() {
  const { data } = useGetMediaSummaryQuery();
  const of = (kind: string) => data?.kinds.find((k) => k.kind === kind);
  const videos = of("video");
  const pdfs = of("document");
  return (
    <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile icon="video" label={`Videos · ${formatBytes(videos?.byte_size ?? 0)}`} value={videos?.count ?? 0} to="/media-library?kind=video" />
      <StatTile icon="fileText" label={`PDFs · ${formatBytes(pdfs?.byte_size ?? 0)}`} value={pdfs?.count ?? 0} to="/media-library?kind=document" />
      <StatTile icon="alert" label="Failed to process" value={data?.failed ?? 0} to="/media-library?status=failed" />
      <StatTile icon="archive" label="Archived" value={data?.archived ?? 0} to="/media-library?archived=true" />
    </div>
  );
}
