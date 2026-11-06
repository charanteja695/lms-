import { ResumeDocumentView } from "@/modules/career/common/components/ResumeDocumentView";
import { useGetResumeVersionQuery } from "@/modules/career/resumes/api/resumesApi";
import { Button, Modal, Spinner } from "@/shared/ui";

export function VersionPreviewDialog({ resumeId, versionNo, onClose }: { resumeId: string; versionNo: number; onClose: () => void }) {
  const { data, isLoading } = useGetResumeVersionQuery({ resumeId, versionNo });
  return (
    <Modal open onClose={onClose} title={`Version ${versionNo}${data?.version.label ? ` · ${data.version.label}` : ""}`} size="lg" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      {isLoading || !data ? <Spinner /> : <ResumeDocumentView document={data.document} />}
    </Modal>
  );
}
