import { useState, useEffect, useRef } from "react";
import { X, Play, AlertCircle, RefreshCw, Film } from "lucide-react";
import { env } from "@/core/config/env";
import { Spinner } from "@/shared/ui";

export interface AdminVideoPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  chapterTitle: string;
  itemTitle?: string;
  mediaId: string | number | null | undefined;
}

export function AdminVideoPreviewModal({
  isOpen,
  onClose,
  chapterTitle,
  itemTitle,
  mediaId,
}: AdminVideoPreviewModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!isOpen) {
      setVideoSrc(null);
      setError(null);
      setIsLoading(true);
      return;
    }

    if (!mediaId) {
      setError("No video file has been uploaded for this chapter yet.");
      setIsLoading(false);
      setVideoSrc(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    // Direct streaming URL from media-service through API Gateway
    const streamUrl = `${env.apiBaseUrl}/media/stream/${mediaId}`;
    setVideoSrc(streamUrl);
  }, [isOpen, mediaId]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleRetry = () => {
    if (!mediaId) return;
    setError(null);
    setIsLoading(true);
    const streamUrl = `${env.apiBaseUrl}/media/stream/${mediaId}?t=${Date.now()}`;
    setVideoSrc(streamUrl);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Video Preview"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/70 backdrop-blur-xs select-none antialiased animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-[#00663C] border border-emerald-200 flex items-center justify-center shrink-0">
              <Play size={17} className="fill-current ml-0.5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900 truncate">
                  {chapterTitle || "Chapter Video Preview"}
                </h3>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-[#00663C] shrink-0">
                  Video Preview
                </span>
              </div>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                {itemTitle || "Uploaded Lecture Video"}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/70 transition-colors cursor-pointer"
            title="Close Preview"
          >
            <X size={18} />
          </button>
        </div>

        {/* Video Canvas Container */}
        <div className="relative flex-1 bg-slate-950 flex items-center justify-center min-h-[320px] sm:min-h-[440px] overflow-hidden">
          {isLoading && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-xs gap-3 text-white">
              <Spinner />
              <p className="text-xs font-semibold text-slate-300">Loading chapter video stream...</p>
            </div>
          )}

          {error ? (
            <div className="max-w-md p-6 text-center text-slate-200 space-y-3">
              <div className="w-12 h-12 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center mx-auto">
                <AlertCircle size={24} />
              </div>
              <h4 className="text-sm font-bold text-white">Video Playback Error</h4>
              <p className="text-xs text-slate-400 leading-relaxed">{error}</p>
              <div className="pt-2 flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={handleRetry}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
                >
                  <RefreshCw size={13} />
                  <span>Retry Stream</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-1.5 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300 hover:bg-slate-700 cursor-pointer transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          ) : videoSrc ? (
            <video
              ref={videoRef}
              key={videoSrc}
              src={videoSrc}
              controls
              autoPlay
              preload="metadata"
              playsInline
              onLoadedData={() => setIsLoading(false)}
              onCanPlay={() => setIsLoading(false)}
              onError={() => {
                setIsLoading(false);
                setError(
                  "Unable to play this video stream. The uploaded file may be corrupted, still processing, or not available on storage."
                );
              }}
              className="w-full h-full max-h-[70vh] object-contain aspect-video"
            >
              <track kind="captions" />
              Your browser does not support HTML5 video playback.
            </video>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-t border-slate-100 bg-slate-50/50 text-xs text-slate-500 shrink-0">
          <div className="flex items-center gap-2">
            <Film size={14} className="text-slate-400" />
            <span className="font-mono text-[11px]">
              Media ID: {mediaId ? String(mediaId) : "N/A"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
