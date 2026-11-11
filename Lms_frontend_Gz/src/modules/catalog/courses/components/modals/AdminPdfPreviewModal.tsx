import { useState, useEffect, useCallback } from "react";
import {
  X,
  FileText,
  AlertCircle,
  RefreshCw,
  Download,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { env } from "@/core/config/env";
import { Spinner } from "@/shared/ui";

export interface AdminPdfPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  chapterTitle: string;
  itemTitle?: string;
  mediaId: string | number | null | undefined;
}

export function AdminPdfPreviewModal({
  isOpen,
  onClose,
  chapterTitle,
  itemTitle,
  mediaId,
}: AdminPdfPreviewModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [page, setPage] = useState<number>(1);
  const [zoom, setZoom] = useState<number>(100);

  const cleanupBlob = useCallback(() => {
    if (blobUrl) {
      URL.revokeObjectURL(blobUrl);
      setBlobUrl(null);
    }
  }, [blobUrl]);

  const loadPdf = useCallback(async () => {
    if (!mediaId) {
      setError("No PDF file has been uploaded for this chapter yet.");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const headers: HeadersInit = {};
      const token =
        localStorage.getItem("token") ||
        localStorage.getItem("access_token") ||
        sessionStorage.getItem("token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const streamUrl = `${env.apiBaseUrl}/media/stream/${mediaId}`;
      const response = await fetch(streamUrl, {
        method: "GET",
        headers,
      });

      if (!response.ok) {
        throw new Error(
          `Failed to load PDF file (${response.status} ${response.statusText})`
        );
      }

      const blob = await response.blob();
      // Ensure mime type is application/pdf
      const pdfBlob =
        blob.type === "application/pdf"
          ? blob
          : new Blob([blob], { type: "application/pdf" });
      const objectUrl = URL.createObjectURL(pdfBlob);
      setBlobUrl(objectUrl);
      setIsLoading(false);
    } catch (err: any) {
      setError(
        err?.message ||
          "Unable to load this PDF document. The file may be missing or inaccessible."
      );
      setIsLoading(false);
    }
  }, [mediaId]);

  useEffect(() => {
    if (!isOpen) {
      cleanupBlob();
      setError(null);
      setIsLoading(true);
      setPage(1);
      setZoom(100);
      return;
    }

    loadPdf();

    return () => {
      cleanupBlob();
    };
  }, [isOpen, mediaId, loadPdf, cleanupBlob]);

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

  const handleDownload = () => {
    if (!blobUrl) return;
    const filename = `${(itemTitle || chapterTitle || "chapter-document")
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, "_")}.pdf`;

    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  };

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(250, prev + 25));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(50, prev - 25));
  };

  const handleResetZoom = () => {
    setZoom(100);
  };

  const handlePrevPage = () => {
    setPage((prev) => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setPage((prev) => prev + 1);
  };

  const iframeSrc = blobUrl ? `${blobUrl}#page=${page}&zoom=${zoom}` : "";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="PDF Preview"
      className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-slate-950/70 backdrop-blur-xs select-none antialiased animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col h-[94vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-[#2563EB] border border-blue-200 flex items-center justify-center shrink-0">
              <FileText size={17} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900 truncate">
                  {chapterTitle || "Chapter PDF Document"}
                </h3>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-blue-100 text-[#2563EB] shrink-0">
                  PDF Preview
                </span>
              </div>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                {itemTitle || "Uploaded Lecture Materials"}
              </p>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {/* Page Navigation */}
            <div className="flex items-center bg-white border border-slate-200 rounded-lg p-0.5 shadow-2xs">
              <button
                type="button"
                onClick={handlePrevPage}
                disabled={page <= 1}
                className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
                title="Previous Page"
              >
                <ChevronLeft size={16} />
              </button>
              <div className="px-2 text-xs font-semibold text-slate-700 min-w-[64px] text-center">
                Page {page}
              </div>
              <button
                type="button"
                onClick={handleNextPage}
                className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 cursor-pointer"
                title="Next Page"
              >
                <ChevronRight size={16} />
              </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center bg-white border border-slate-200 rounded-lg p-0.5 shadow-2xs">
              <button
                type="button"
                onClick={handleZoomOut}
                disabled={zoom <= 50}
                className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
                title="Zoom Out"
              >
                <ZoomOut size={16} />
              </button>
              <button
                type="button"
                onClick={handleResetZoom}
                className="px-2 text-xs font-mono font-medium text-slate-700 hover:bg-slate-100 rounded cursor-pointer min-w-[48px] text-center"
                title="Reset Zoom to 100%"
              >
                {zoom}%
              </button>
              <button
                type="button"
                onClick={handleZoomIn}
                disabled={zoom >= 250}
                className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
                title="Zoom In"
              >
                <ZoomIn size={16} />
              </button>
            </div>

            {/* Download Button */}
            <button
              type="button"
              onClick={handleDownload}
              disabled={!blobUrl || isLoading || Boolean(error)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-xs transition-colors"
              title="Download PDF"
            >
              <Download size={14} />
              <span className="hidden sm:inline">Download PDF</span>
            </button>

            {/* Close */}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/70 transition-colors cursor-pointer ml-1"
              title="Close Preview"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* PDF Viewer Container */}
        <div className="relative flex-1 bg-slate-100 flex items-center justify-center overflow-hidden">
          {isLoading && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/90 backdrop-blur-xs gap-3">
              <Spinner />
              <p className="text-xs font-semibold text-slate-600">
                Loading PDF document...
              </p>
            </div>
          )}

          {error ? (
            <div className="max-w-md p-6 text-center text-slate-700 space-y-3">
              <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto border border-rose-200">
                <AlertCircle size={24} />
              </div>
              <h4 className="text-sm font-bold text-slate-900">
                PDF Preview Unavailable
              </h4>
              <p className="text-xs text-slate-500 leading-relaxed">{error}</p>
              <div className="pt-2 flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={loadPdf}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
                >
                  <RefreshCw size={13} />
                  <span>Retry Loading</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          ) : blobUrl ? (
            <iframe
              key={`${blobUrl}-${page}-${zoom}`}
              src={iframeSrc}
              title={`PDF - ${chapterTitle}`}
              className="w-full h-full border-0 bg-slate-200"
            />
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 border-t border-slate-100 bg-slate-50/50 text-xs text-slate-500 shrink-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px]">
              Media ID: {mediaId ? String(mediaId) : "N/A"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownload}
              disabled={!blobUrl || isLoading || Boolean(error)}
              className="px-3 py-1 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 cursor-pointer shadow-2xs"
            >
              Save a Copy
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1 rounded-lg bg-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-300 cursor-pointer transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
