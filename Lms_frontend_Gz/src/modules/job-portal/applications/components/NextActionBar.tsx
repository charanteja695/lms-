import { Link } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate } from "@/core/lib/format";
import { useRespondToOfferMutation } from "@/modules/job-portal/applications/api/myApplicationsApi";
import type { MyApplication } from "@/modules/job-portal/applications/types";
import { formatCtc } from "@/modules/job-portal/common/format";
import { Button, ConfirmDialog } from "@/shared/ui";

/** Where each kind of next step is done in the app. */
const WHERE = { assessment: "/my-tests", ai_interview: "/interviews" } as const;

/** The one thing the candidate must do now (the server decides which), with the button that does it. */
export function NextActionBar({ application }: { application: MyApplication }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [respond, { isLoading }] = useRespondToOfferMutation();
  const action = application.next_action;
  if (!action) return null;
  const offer = application.offer;
  const answer = (accept: boolean) =>
    confirm.ask(
      { title: accept ? "Accept this offer?" : "Decline this offer?", description: accept ? "The company is told you'll join." : "This can't be undone.", confirmLabel: accept ? "Accept" : "Decline", tone: accept ? "primary" : "danger" },
      async () => { await respond({ id: application.application_id, accept }).unwrap().then(() => notify.success(accept ? "Offer accepted" : "Offer declined"), notify.apiError); },
    );

  return (
    <div className={action.kind === "offer" ? "flex flex-wrap items-center gap-3 rounded-xl bg-brand-50 p-3.5 ring-1 ring-brand-200" : "flex flex-wrap items-center gap-3 rounded-xl bg-accent-50 p-3.5 ring-1 ring-accent-200"}>
      <div className="min-w-[200px] flex-1 text-sm text-slate-700">
        <p className="font-bold text-navy-950">{action.label}</p>
        <p>
          {action.kind === "offer" && offer ? `${offer.role_title} · ${formatCtc(offer.ctc, offer.currency)} a year${offer.joining_date ? ` · joining ${formatDate(offer.joining_date)}` : ""}. ` : ""}
          {action.detail}{action.due_at ? ` Reply by ${formatDate(action.due_at)}.` : ""}
        </p>
      </div>
      {action.kind === "offer" ? (
        <div className="flex gap-2">
          <Button loading={isLoading} onClick={() => answer(true)}>Accept offer</Button>
          <Button variant="secondary" disabled={isLoading} onClick={() => answer(false)}>Decline</Button>
        </div>
      ) : (
        <div className="flex gap-2">
          <Link to={WHERE[action.kind]} className="inline-flex h-10 items-center rounded-xl bg-brand-700 px-4 text-sm font-bold text-white hover:bg-brand-800">{action.label}</Link>
          {action.kind === "ai_interview" && <Link to="/interviews/practice" className="inline-flex h-10 items-center rounded-xl px-3 text-sm font-semibold text-navy-950 ring-1 ring-slate-200 hover:bg-white">Practise first</Link>}
        </div>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
