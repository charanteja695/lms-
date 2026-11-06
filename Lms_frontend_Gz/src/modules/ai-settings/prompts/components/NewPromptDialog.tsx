import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import type { Capability } from "@/modules/ai-settings/common/types";
import { useCreatePromptMutation } from "@/modules/ai-settings/prompts/api/promptsApi";
import { Button, Field, Input, Modal, Select, Textarea } from "@/shared/ui";

const CAPABILITIES = [
  { value: "chat", label: "Chat (a conversation or a single answer)" },
  { value: "embedding", label: "Search (embeddings)" },
];

/** Register a prompt by its key (e.g. tutor.explain_concept); its text is written as a version afterwards. */
export function NewPromptDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const notify = useNotify();
  const navigate = useNavigate();
  const [create, { isLoading }] = useCreatePromptMutation();
  const [form, setForm] = useState({ key: "", owner_service: "", capability: "chat" as Capability, description: "" });
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const valid = /^[a-z0-9]+([._-][a-z0-9]+)*$/.test(form.key) && form.owner_service.trim().length > 1;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New prompt"
      description="Give it a key the calling service uses. You write its text as a first version next."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            disabled={!valid}
            loading={isLoading}
            onClick={() => void create({ ...form, owner_service: form.owner_service.trim() }).unwrap().then((p) => navigate(`/ai/prompts/${encodeURIComponent(p.key)}`), notify.apiError)}
          >
            Create prompt
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Key" required hint="Lower case, dots between words, e.g. tutor.explain_concept">{(p) => <Input {...p} value={form.key} maxLength={80} onChange={(e) => set({ key: e.target.value.toLowerCase() })} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Used by service" required hint="e.g. ai-tutor-service">{(p) => <Input {...p} value={form.owner_service} maxLength={60} onChange={(e) => set({ owner_service: e.target.value.toLowerCase() })} />}</Field>
          <Field label="Kind">{(p) => <Select {...p} value={form.capability} options={CAPABILITIES} onChange={(e) => set({ capability: e.target.value as Capability })} />}</Field>
        </div>
        <Field label="What it is for">{(p) => <Textarea {...p} rows={3} maxLength={500} value={form.description} onChange={(e) => set({ description: e.target.value })} />}</Field>
      </div>
    </Modal>
  );
}
