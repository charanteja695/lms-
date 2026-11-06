import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useActivateTemplateMutation, useArchiveTemplateMutation, usePreviewTemplateMutation } from "@/modules/certificates/templates/api/templatesApi";
import type { CertificateTemplate } from "@/modules/certificates/templates/types";
import { Button, ConfirmDialog } from "@/shared/ui";

export function TemplateLifecycleActions({ template, canAuthor, canPublish }: { template: CertificateTemplate; canAuthor: boolean; canPublish: boolean }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [preview, { isLoading: previewing }] = usePreviewTemplateMutation();
  const [activate] = useActivateTemplateMutation();
  const [archive] = useArchiveTemplateMutation();

  const run = async (work: () => Promise<unknown>, success: string) => {
    try {
      await work();
      notify.success(success);
    } catch (error) {
      notify.apiError(error);
    }
  };

  const openPreview = async () => {
    try {
      const url = await preview(template.template_id).unwrap();
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="secondary" icon="eye" loading={previewing} onClick={() => void openPreview()}>
        Preview PDF
      </Button>
      {canAuthor && template.status === "draft" && (
        <Button variant="secondary" icon="edit" onClick={() => navigate(`/certificates/templates/${template.template_id}/edit`)}>
          Edit
        </Button>
      )}
      {canAuthor && template.status !== "draft" && (
        <Button variant="secondary" icon="plus" onClick={() => navigate("/certificates/templates/new", { state: { copyFrom: template } })}>
          Copy to new draft
        </Button>
      )}
      {canPublish && template.status === "draft" && (
        <Button
          icon="check"
          onClick={() =>
            confirm.ask(
              { title: "Activate this template?", description: "New certificates for its course use it from now on; the currently active one is archived.", confirmLabel: "Activate", tone: "primary" },
              () => run(() => activate(template.template_id).unwrap(), "Template activated"),
            )
          }
        >
          Activate
        </Button>
      )}
      {canPublish && template.status !== "archived" && (
        <Button
          variant="danger"
          icon="archive"
          onClick={() =>
            confirm.ask({ title: "Archive this template?", description: "It can't be activated again; copy it into a new draft instead.", confirmLabel: "Archive" }, () =>
              run(() => archive(template.template_id).unwrap(), "Template archived"),
            )
          }
        >
          Archive
        </Button>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
