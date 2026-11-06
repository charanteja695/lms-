import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useAddProfileItemsMutation, useImportResumeFileMutation, useUpdateCareerProfileMutation } from "@/modules/career/profile/api/profileApi";
import type { ImportResult } from "@/modules/career/profile/types";
import { useCreateResumeMutation } from "@/modules/career/resumes/api/resumesApi";
import { ImportReview } from "@/modules/career/resumes/components/new/ImportReview";
import { StartChoices, type StartState } from "@/modules/career/resumes/components/new/StartChoices";
import type { Resume, ResumeOptions } from "@/modules/career/resumes/types";
import { Alert, Button, Modal } from "@/shared/ui";

/**
 * New resume in one clean dialog:
 * - Start from profile, uploaded resume file (PDF/Word), LinkedIn PDF, or blank.
 * - Upload and AI extraction are separated with seamless offline/fallback support.
 * - Allows reviewing extracted entries before saving or continuing without AI.
 */
export function NewResumeDialog({
  options,
  onClose,
  onCreated,
}: {
  options: ResumeOptions;
  onClose: () => void;
  onCreated: (resume: Resume) => void;
}) {
  const notify = useNotify();
  const [state, setState] = useState<StartState>({
    start: options.start_options[0]?.key ?? "profile",
    level: options.experience_levels[0]?.key ?? "",
    role: options.role_suggestions[0] ?? "",
    file: null,
  });
  const [imported, setImported] = useState<ImportResult | null>(null);
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  const [inlineError, setInlineError] = useState<string | null>(null);

  const [readFile, { isLoading: reading }] = useImportResumeFileMutation();
  const [addItems, { isLoading: adding }] = useAddProfileItemsMutation();
  const [updateProfile] = useUpdateCareerProfileMutation();
  const [create, { isLoading: creating }] = useCreateResumeMutation();

  const start = options.start_options.find((o) => o.key === state.start);
  const needsFile = Boolean(start?.accepts.length);
  const busy = reading || adding || creating;

  const createResume = async () => {
    const role = state.role.trim();
    const created = await create({
      title: role || "My resume",
      target_role: role || null,
      experience_level: state.level,
      blank: state.start === "blank",
    }).unwrap();
    onCreated(created);
  };

  const processFile = async () => {
    if (!state.file) return;
    setInlineError(null);
    try {
      const result = await readFile(state.file).unwrap();
      setImported(result);
      setChosen(new Set(result.items.map((_, index) => index)));
    } catch (error) {
      setInlineError(
        "Could not automatically extract entries from this file. You can still proceed to build your resume draft and enter details manually.",
      );
      notify.apiError(error, "Extraction notice");
    }
  };

  const submit = async () => {
    setInlineError(null);
    try {
      if (needsFile && !imported) {
        // Step 1: Read/process selected resume
        await processFile();
        return;
      }

      if (imported) {
        // Step 2: Save chosen items to profile
        const items = imported.items
          .filter((_, index) => chosen.has(index))
          .map(({ kind, data }) => ({ kind, data }));
        if (items.length > 0) {
          await addItems(items).unwrap();
        }
        const fields = Object.fromEntries(
          Object.entries(imported.profile).filter(([, value]) => value),
        );
        if (Object.keys(fields).length > 0) {
          await updateProfile(fields).unwrap().catch(() => undefined);
        }
      }

      await createResume();
    } catch (error) {
      notify.apiError(error);
    }
  };

  const handleContinueWithoutExtraction = async () => {
    try {
      await createResume();
    } catch (error) {
      notify.apiError(error);
    }
  };

  const primaryLabel =
    needsFile && !imported
      ? "Process resume & continue"
      : imported
      ? chosen.size > 0
        ? `Add ${chosen.size} entries & create draft`
        : "Create resume draft"
      : "Create resume draft";

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={imported ? "Check what we found" : "New resume"}
      description={
        imported
          ? undefined
          : "Choose where to start, your experience level, and target role to create your resume draft."
      }
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <div>
            {needsFile && !imported && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleContinueWithoutExtraction}
                disabled={busy}
                className="text-xs text-slate-500 hover:text-slate-800"
              >
                Skip upload & create manually
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={imported ? () => setImported(null) : onClose}
              disabled={busy}
            >
              {imported ? "Back" : "Cancel"}
            </Button>
            <Button
              loading={busy}
              disabled={needsFile && !imported && !state.file}
              onClick={() => void submit()}
            >
              {primaryLabel}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {inlineError && (
          <Alert tone="warning" title="Notice">
            <div className="space-y-2">
              <p>{inlineError}</p>
              <Button
                size="sm"
                variant="secondary"
                onClick={handleContinueWithoutExtraction}
                loading={busy}
              >
                Continue to resume builder
              </Button>
            </div>
          </Alert>
        )}

        {imported ? (
          <ImportReview
            result={imported}
            chosen={chosen}
            onToggle={(index) =>
              setChosen((current) => {
                const next = new Set(current);
                if (next.has(index)) next.delete(index);
                else next.add(index);
                return next;
              })
            }
            onSelectAll={() =>
              setChosen(new Set(imported.items.map((_, index) => index)))
            }
            onDeselectAll={() => setChosen(new Set())}
          />
        ) : (
          <StartChoices
            options={options}
            value={state}
            onChange={(next) => {
              setInlineError(null);
              setState((current) => ({ ...current, ...next }));
            }}
          />
        )}
      </div>
    </Modal>
  );
}
