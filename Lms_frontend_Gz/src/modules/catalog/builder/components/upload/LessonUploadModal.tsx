import { useRef, useState, type DragEvent } from "react";

import { cn } from "@/core/lib/cn";
import { UploadRow } from "@/modules/catalog/builder/components/upload/UploadRow";
import { ACCEPT, type TopicRef, type UploadKind, useLessonUploads } from "@/modules/catalog/builder/hooks/useLessonUploads";
import { Button, Icon, Modal, Tabs } from "@/shared/ui";

const HINT: Record<UploadKind, string> = {
  video: "MP4, MOV or WebM · up to 5 GB each · several at once",
  pdf: "PDF · up to 50 MB each · several at once",
};

/** Drop videos or PDFs; each file becomes one lesson of the topic, in the order dropped. */
export function LessonUploadModal({ topic, topicLabel, initialKind, onClose }: { topic: TopicRef; topicLabel: string; initialKind: UploadKind; onClose: () => void }) {
  const [kind, setKind] = useState<UploadKind>(initialKind);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const { uploads, addFiles, cancel, dismiss, busy } = useLessonUploads(topic);

  const accept = (files: FileList | null) => {
    const list = [...(files ?? [])].filter((file) => (kind === "pdf" ? file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf") : file.type.startsWith("video/")));
    if (list.length) addFiles(list, kind);
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files);
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Add lessons"
      description={topicLabel}
      footer={
        <>
          <span className="mr-auto self-center text-xs text-slate-500">{busy ? "Uploads keep going if you close this." : "Each file becomes one lesson, in this order."}</span>
          <Button onClick={onClose}>Done</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Tabs<UploadKind>
          variant="pills"
          value={kind}
          onChange={setKind}
          tabs={[
            { value: "video", label: "Videos" },
            { value: "pdf", label: "PDFs" },
          ]}
        />
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn("flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition-colors", dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-50/60")}
        >
          <span className={cn("flex h-12 w-12 items-center justify-center rounded-2xl", kind === "pdf" ? "bg-accent-50 text-accent-700" : "bg-navy-50 text-navy-700")}>
            <Icon name="upload" size={22} />
          </span>
          <p className="text-[15px] font-bold text-navy-950">Drop {kind === "pdf" ? "PDFs" : "videos"} here</p>
          <p className="text-sm text-slate-600">
            or{" "}
            <button type="button" onClick={() => input.current?.click()} className="font-bold text-brand-700 hover:text-brand-800">
              choose files
            </button>{" "}
            · {HINT[kind]}
          </p>
          <input ref={input} type="file" multiple accept={ACCEPT[kind]} className="sr-only" onChange={(event) => { accept(event.target.files); event.target.value = ""; }} />
        </div>
        {uploads.length > 0 && (
          <ul className="space-y-2.5" aria-label="Uploads">
            {uploads.map((upload) => (
              <UploadRow key={upload.id} upload={upload} onCancel={() => cancel(upload.id)} onDismiss={() => dismiss(upload.id)} />
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}
