import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useTutorRights } from "@/modules/ai-tutor/common/hooks/useTutorRights";
import { useArchiveFaqMutation, usePublishFaqMutation, useUpdateFaqMutation } from "@/modules/ai-tutor/faq/api/faqApi";
import type { FaqEntry } from "@/modules/ai-tutor/faq/types";
import { Button, Field, Input, Modal, Textarea } from "@/shared/ui";

/** Edit an entry's wording, publish a draft, or archive it. An archived entry is read-only (FAQ_ARCHIVED). */
export function FaqEntryDialog({ entry, onClose }: { entry: FaqEntry; onClose: () => void }) {
  const notify = useNotify();
  const [question, setQuestion] = useState(entry.question);
  const [answer, setAnswer] = useState(entry.answer);
  const [update, { isLoading: saving }] = useUpdateFaqMutation();
  const [publish, { isLoading: publishing }] = usePublishFaqMutation();
  const [archive, { isLoading: archiving }] = useArchiveFaqMutation();
  const rights = useTutorRights();
  const archived = entry.status === "archived";
  const editable = !archived && rights.canEditFaq;
  const busy = saving || publishing || archiving;

  const run = async (work: () => Promise<unknown>, message: string) => {
    try {
      await work();
      notify.success(message);
      onClose();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={archived ? "Archived FAQ entry" : editable ? "Edit FAQ entry" : "FAQ entry"}
      size="lg"
      footer={
        <>
          {!archived && rights.canArchiveFaq && (
            <Button variant="danger" icon="archive" disabled={busy} loading={archiving} onClick={() => void run(() => archive(entry.faq_id).unwrap(), "Entry archived")}>
              Archive
            </Button>
          )}
          <span className="flex-1" />
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Close
          </Button>
          {editable && (
            <Button variant="secondary" loading={saving} disabled={busy} onClick={() => void run(() => update({ faqId: entry.faq_id, question, answer }).unwrap(), "Entry saved")}>
              Save
            </Button>
          )}
          {entry.status === "draft" && rights.canEditFaq && (
            <Button
              loading={publishing}
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  if (question !== entry.question || answer !== entry.answer) await update({ faqId: entry.faq_id, question, answer }).unwrap();
                  await publish(entry.faq_id).unwrap();
                }, "Entry published")
              }
            >
              Publish
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Question" required>{(props) => <Input {...props} value={question} disabled={!editable} maxLength={500} onChange={(event) => setQuestion(event.target.value)} />}</Field>
        <Field label="Answer" required>
          {(props) => <Textarea {...props} rows={8} value={answer} disabled={!editable} maxLength={4000} onChange={(event) => setAnswer(event.target.value)} />}
        </Field>
        <p className="text-xs text-slate-500">Marked helpful {entry.helpful_count} time{entry.helpful_count === 1 ? "" : "s"}.</p>
      </div>
    </Modal>
  );
}
