import { useState } from "react";

import { formatDateTime } from "@/core/lib/format";
import { useNotify } from "@/core/hooks/useNotify";
import { useGetSnapshotUrlMutation } from "@/modules/proctoring/cases/api/casesApi";
import type { CaseSnapshot } from "@/modules/proctoring/cases/types";
import type { SnapshotKind } from "@/modules/proctoring/common/types";
import { Badge, Button, Card, Icon } from "@/shared/ui";

const KIND_LABELS: Record<SnapshotKind, string> = {
  id_photo: "ID photo",
  face_enrol: "Face scan",
  liveness: "Face movement",
  periodic: "Photo",
  screen: "Screen",
  audio: "Audio clip",
  video: "Recording",
};
const POSES = ["", "left", "right", "up", "down"];

/** The attempt's evidence: the test recording (played here, piece by piece) and every photo, clip and capture. */
export function CaseSnapshotsCard({ caseId, snapshots }: { caseId: string; snapshots: CaseSnapshot[] }) {
  const notify = useNotify();
  const [getUrl] = useGetSnapshotUrlMutation();
  const [playing, setPlaying] = useState<{ id: string; url: string } | null>(null);
  const recording = snapshots.filter((s) => s.kind === "video").sort((a, b) => a.sequence - b.sequence);
  const others = snapshots.filter((s) => s.kind !== "video");

  const link = async (snapshotId: string) => {
    try {
      return (await getUrl({ caseId, snapshotId }).unwrap()).url; // every view is logged by the server
    } catch (error) {
      notify.apiError(error);
      return null;
    }
  };
  const play = async (snapshotId: string) => {
    const url = await link(snapshotId);
    if (url) setPlaying({ id: snapshotId, url });
  };
  const open = async (snapshotId: string) => {
    const url = await link(snapshotId);
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="space-y-6">
      <Card title="Test recording" description={recording.length ? `${recording.length} piece${recording.length === 1 ? "" : "s"}, in order. Each plays on its own.` : undefined}>
        {recording.length === 0 ? (
          <p className="text-sm text-slate-500">No recording for this attempt.</p>
        ) : (
          <div className="space-y-4">
            {playing && (
              <video
                key={playing.id}
                src={playing.url}
                controls
                autoPlay
                className="aspect-video w-full rounded-xl bg-navy-950"
                onEnded={() => {
                  const next = recording[recording.findIndex((r) => r.snapshot_id === playing.id) + 1];
                  if (next) void play(next.snapshot_id); // carry on to the next piece
                }}
              />
            )}
            <div className="flex flex-wrap gap-2">
              {recording.map((piece) => (
                <Button
                  key={piece.snapshot_id}
                  variant={playing?.id === piece.snapshot_id ? "primary" : "secondary"}
                  size="sm"
                  icon="play"
                  onClick={() => void play(piece.snapshot_id)}
                >
                  Part {piece.sequence} · {formatDateTime(piece.taken_at).split(", ").pop()}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card title={`Photos and clips (${others.length})`}>
        {others.length === 0 ? (
          <p className="text-sm text-slate-500">None captured.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {others.map((snapshot) => (
              <li key={snapshot.snapshot_id} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
                <span className="flex min-w-0 flex-wrap items-center gap-2">
                  <Badge tone={snapshot.flagged ? "red" : "gray"}>{KIND_LABELS[snapshot.kind] ?? snapshot.kind}</Badge>
                  {snapshot.kind === "liveness" ? <span className="capitalize">{POSES[snapshot.sequence] ?? ""}</span> : snapshot.sequence > 0 && <span>#{snapshot.sequence}</span>}
                  <span className="text-slate-500">{formatDateTime(snapshot.taken_at)}</span>
                  {snapshot.skip_reason && <span className="text-xs text-slate-400">({snapshot.skip_reason})</span>}
                </span>
                <Button variant="ghost" size="sm" onClick={() => void open(snapshot.snapshot_id)}>
                  <Icon name="eye" size={15} /> View
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
