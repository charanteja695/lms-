import { useCallback, useEffect, useRef, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useUpdateResumeMutation } from "@/modules/career/resumes/api/resumesApi";
import type { Draft, ResumeDetail, ResumeUpdateBody } from "@/modules/career/resumes/types";

export type Meta = Pick<ResumeUpdateBody, "title" | "target_role" | "template_key" | "job_description">;
export type SaveStatus = "saved" | "pending" | "saving" | "error";

const DELAY_MS = 800;

/**
 * The editor's working copy, saved automatically a moment after the student stops typing (no Save button), like the
 * resume builders people know. Each save sends the revision the last save returned, so quick edits never collide with
 * themselves; if the draft changed in another tab the server answers STALE_DRAFT and the newer one is loaded.
 */
export function useResumeDraft(detail: ResumeDetail | undefined, refetch: () => unknown) {
  const notify = useNotify();
  const [update] = useUpdateResumeMutation();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [meta, setMeta] = useState<Meta>({});
  const [status, setStatus] = useState<SaveStatus>("saved");
  const revision = useRef<number | null>(null);
  const edits = useRef(0);  // bumped on every change; a save only clears "pending" if nothing changed meanwhile
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef<{ draft: Draft | null; meta: Meta }>({ draft: null, meta: {} });

  useEffect(() => {
    if (!detail || status !== "saved") return;
    revision.current = detail.resume.draft_revision;
    setDraft(detail.draft);
    const next = { title: detail.resume.title, target_role: detail.resume.target_role, template_key: detail.resume.template_key, job_description: detail.job_description };
    setMeta(next);
    latest.current = { draft: detail.draft, meta: next };
  }, [detail, status]);

  const send = useCallback(async (extra: Partial<ResumeUpdateBody> = {}, withDraft = true) => {
    if (!detail || revision.current == null) return;
    const mark = edits.current;
    const { draft: current, meta: currentMeta } = latest.current;
    setStatus("saving");
    try {
      const saved = await update({
        resumeId: detail.resume.resume_id,
        body: {
          expected_revision: revision.current, ...currentMeta, title: currentMeta.title?.trim() || detail.resume.title,
          ...(withDraft && current ? { draft: current } : {}), ...extra,
        },
      }).unwrap();
      revision.current = saved.draft_revision;
      setStatus(edits.current === mark ? "saved" : "pending");
    } catch (error) {
      if (toApiError(error).code === "STALE_DRAFT") {
        notify.error("This resume changed in another tab", "Loaded the newer copy.");
        setStatus("saved");
        refetch();
      } else {
        setStatus("error");
        notify.apiError(error, "Not saved");
      }
    }
  }, [detail, update, notify, refetch]);

  const schedule = useCallback(() => {
    edits.current += 1;
    setStatus("pending");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void send(), DELAY_MS);
  }, [send]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const change = (next: Draft) => {
    setDraft(next);
    latest.current = { ...latest.current, draft: next };
    schedule();
  };
  const changeMeta = (next: Partial<Meta>) => {
    const merged = { ...latest.current.meta, ...next };
    setMeta(merged);
    latest.current = { ...latest.current, meta: merged };
    schedule();
  };
  /** The server puts the sections in the new level's order, so this saves without the local draft and then reloads it. */
  const changeLevel = async (level: string) => {
    if (timer.current) clearTimeout(timer.current);
    if (status === "pending") await send();
    await send({ experience_level: level }, false);
  };

  return { draft, meta, status, change, changeMeta, changeLevel, retry: () => void send() };
}
