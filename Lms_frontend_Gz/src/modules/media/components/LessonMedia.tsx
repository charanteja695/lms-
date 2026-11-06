import { useEffect, useState } from "react";

import { env } from "@/core/config/env";
import { useCreatePlaybackMutation } from "@/modules/media/api/mediaApi";
import { Button, Icon, Spinner } from "@/shared/ui";

/**
 * Plays a lesson video or shows a lesson PDF from media-service. A short-lived playback link is issued when it
 * opens; the link redirects to signed storage, so the file never passes through our servers.
 */
export function LessonMedia({ mediaId, kind, title, onEnded }: { mediaId: string; kind: "video" | "pdf"; title: string; onEnded?: () => void }) {
  const [createPlayback] = useCreatePlaybackMutation();
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setSrc(null);
    setFailed(false);
    createPlayback(mediaId)
      .unwrap()
      .then((playback) => live && setSrc(`${env.apiBaseUrl}${playback.playback_url}`))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [createPlayback, mediaId]);

  if (failed) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-2xl bg-ink-950 p-6 text-center text-slate-200">
        <Icon name="alert" size={26} />
        <p className="text-sm font-semibold">This {kind === "pdf" ? "PDF" : "video"} could not be opened.</p>
        <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>Try again</Button>
      </div>
    );
  }
  if (!src) {
    return (
      <div className="flex aspect-video w-full items-center justify-center rounded-2xl bg-ink-950 text-white">
        <Spinner />
      </div>
    );
  }
  if (kind === "pdf") {
    return (
      <div className="space-y-2">
        <iframe title={title} src={src} className="h-[75vh] min-h-[480px] w-full rounded-2xl border border-slate-200 bg-white shadow-card" />
        <a href={src} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:text-brand-800">
          <Icon name="fileText" size={15} />
          Open the PDF in a new tab
        </a>
      </div>
    );
  }
  return (
    <video
      key={src}
      src={src}
      controls
      preload="metadata"
      controlsList="nodownload"
      onEnded={onEnded}
      className="aspect-video w-full rounded-2xl bg-ink-950 shadow-card"
    >
      <track kind="captions" />
    </video>
  );
}
