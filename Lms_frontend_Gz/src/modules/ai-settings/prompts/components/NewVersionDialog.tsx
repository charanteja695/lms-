import { useMemo, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreatePromptVersionMutation } from "@/modules/ai-settings/prompts/api/promptsApi";
import { Alert, Badge, Button, Field, Input, Modal, Textarea } from "@/shared/ui";

/** {{placeholders}} in the template: the server requires each one declared, so they are read from the text itself. */
export function placeholdersIn(template: string): string[] {
  return [...new Set([...template.matchAll(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g)].map((m) => m[1]!))];
}

/** Draft a new version of a prompt. It starts as a draft; another AI manager activates it. */
export function NewVersionDialog({ promptKey, initialTemplate, onClose }: { promptKey: string; initialTemplate: string; onClose: () => void }) {
  const notify = useNotify();
  const [create, { isLoading }] = useCreatePromptVersionMutation();
  const [template, setTemplate] = useState(initialTemplate);
  const [tools, setTools] = useState("");
  const [params, setParams] = useState("");
  const variables = useMemo(() => placeholdersIn(template), [template]);
  const parsed = useMemo(() => { try { return params.trim() ? (JSON.parse(params) as Record<string, unknown>) : {}; } catch { return null; } }, [params]);
  const valid = template.trim().length > 0 && parsed !== null;

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="New version"
      description={`Of ${promptKey}. Saved as a draft: it is not used until another AI manager activates it.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            disabled={!valid}
            loading={isLoading}
            onClick={() => void create({ key: promptKey, body: { template, variables, allowed_tools: tools.split(",").map((t) => t.trim()).filter(Boolean), model_params: parsed ?? {} } })
              .unwrap().then(() => { notify.success("Draft saved"); onClose(); }, notify.apiError)}
          >
            Save draft
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Instructions" required hint="Put values the service fills in as {{name}}, e.g. {{course_title}}.">
          {(p) => <Textarea {...p} rows={10} className="font-mono text-[13px]" value={template} maxLength={20000} onChange={(e) => setTemplate(e.target.value)} />}
        </Field>
        <div>
          <p className="mb-1.5 text-sm font-semibold text-slate-800">Values it expects</p>
          {variables.length ? <div className="flex flex-wrap gap-1.5">{variables.map((v) => <Badge key={v} tone="indigo">{v}</Badge>)}</div> : <p className="text-sm text-slate-500">None yet.</p>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Tools it may call" hint="Comma-separated; empty for none.">{(p) => <Input {...p} value={tools} onChange={(e) => setTools(e.target.value)} />}</Field>
          <Field label="Model settings (JSON)" hint='Optional, e.g. {"temperature": 0.3}'>{(p) => <Input {...p} className="font-mono text-[13px]" value={params} invalid={parsed === null} onChange={(e) => setParams(e.target.value)} />}</Field>
        </div>
        {parsed === null && <Alert tone="error">Model settings must be valid JSON, or empty.</Alert>}
      </div>
    </Modal>
  );
}
