import { useEffect, useState } from "react";

import { env } from "@/core/config/env";
import { cn } from "@/core/lib/cn";
import { useCreatePlaybackMutation } from "@/modules/media/api/mediaApi";
import { Icon } from "@/shared/ui";

export function CourseThumbnail({
  thumbnailMediaId,
  title,
  badge,
  className,
}: {
  thumbnailMediaId?: string | null;
  title: string;
  badge?: string | null;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [createPlayback] = useCreatePlaybackMutation();

  useEffect(() => {
    let active = true;
    setSrc(null);
    if (!thumbnailMediaId) return;
    createPlayback(thumbnailMediaId)
      .unwrap()
      .then((pb) => {
        if (!active || !pb?.playback_url) return;
        const base = env.apiBaseUrl.replace(/\/$/, "");
        setSrc(pb.playback_url.startsWith("http") ? pb.playback_url : `${base}${pb.playback_url}`);
      })
      .catch(() => {
        if (active) setSrc(null);
      });
    return () => {
      active = false;
    };
  }, [thumbnailMediaId, createPlayback]);

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl bg-gradient-to-br from-navy-900 via-brand-800 to-brand-600",
        className,
      )}
    >
      {src ? (
        <img
          src={src}
          alt={title}
          className="h-full w-full object-cover"
          onError={() => setSrc(null)}
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center p-4 text-white/90">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15 backdrop-blur-sm">
            <Icon name="graduation" size={24} className="text-white" />
          </div>
          <span className="mt-2 line-clamp-1 max-w-full text-center text-xs font-medium text-brand-100">
            {title}
          </span>
        </div>
      )}
      {badge && (
        <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-0.5 text-[11px] font-semibold text-navy-900 shadow-sm">
          {badge}
        </span>
      )}
    </div>
  );
}
