import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import { FAQ_SCOPE_LABELS } from "@/modules/ai-tutor/common/labels";
import { useTutorRights } from "@/modules/ai-tutor/common/hooks/useTutorRights";
import type { FaqScope } from "@/modules/ai-tutor/common/types";
import { useCreateFaqMutation } from "@/modules/ai-tutor/faq/api/faqApi";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { Button, EntityPicker, Field, Input, Modal, Select, Textarea } from "@/shared/ui";

/** Scopes this person may write, per ai-tutor-service's can_manage_faq: staff their institution, authors a course, support managers any. */
function useWritableScopes(): FaqScope[] {
  const rights = useTutorRights();
  if (rights.support) return ["platform", "organization", "course"];
  return [...(rights.author ? (["course"] as const) : []), ...(rights.isStaff ? (["organization"] as const) : [])];
}

export function FaqCreateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const notify = useNotify();
  const { user } = useAuth();
  const { support } = useTutorRights();
  const scopes = useWritableScopes();
  const [scope, setScope] = useState<FaqScope>(scopes[0] ?? "course");
  const [course, setCourse] = useState({ id: "", label: "" });
  const [org, setOrg] = useState({ id: "", label: "" });
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [create, { isLoading }] = useCreateFaqMutation();
  const organizationId = support ? org.id : (user?.institution?.organization_id ?? "");

  const submit = async () => {
    try {
      await create({
        scope,
        organization_id: scope === "organization" ? organizationId || null : null,
        course_id: scope === "course" ? course.id || null : null,
        question,
        answer,
      }).unwrap();
      notify.success("Draft added", "Publish it when it's ready for students.");
      onClose();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New FAQ entry"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button loading={isLoading} onClick={() => void submit()}>
            Add draft
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {scopes.length > 1 && (
          <Field label="Visible to">
            {(props) => <Select {...props} value={scope} options={scopes.map((value) => ({ value, label: FAQ_SCOPE_LABELS[value] }))} onChange={(event) => setScope(event.target.value as FaqScope)} />}
          </Field>
        )}
        {scope === "course" && <EntityPicker label="Course" required value={course.id} selectedLabel={course.label} useOptions={useCourseOptions} onChange={(id, label) => setCourse({ id, label })} />}
        {scope === "organization" && support && (
          <EntityPicker label="Institution" required value={org.id} selectedLabel={org.label} useOptions={useInstitutionOptions} onChange={(id, label) => setOrg({ id, label })} />
        )}
        {scope === "organization" && !support && <p className="text-sm text-slate-500">Visible to students of {user?.institution?.name ?? "your institution"}.</p>}
        <Field label="Question" required>{(props) => <Input {...props} value={question} maxLength={500} onChange={(event) => setQuestion(event.target.value)} />}</Field>
        <Field label="Answer" required>{(props) => <Textarea {...props} rows={6} value={answer} maxLength={4000} onChange={(event) => setAnswer(event.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
