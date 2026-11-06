import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import type { Ticket } from "@/modules/support/common/types";
import { useTicketActionMutation } from "@/modules/support/agent/api/agentTicketsApi";
import { AssignDialog } from "@/modules/support/agent/components/detail/AssignDialog";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { Button } from "@/shared/ui";

/** Claim / assign / release / resolve / reopen / close, offered for the ticket's current status; the server re-checks every one. */
export function TicketActions({ ticket }: { ticket: Ticket }) {
  const notify = useNotify();
  const { user } = useAuth();
  const { isManager, isHead } = useSupportRights();
  const [act, { isLoading, originalArgs }] = useTicketActionMutation();
  const [assigning, setAssigning] = useState(false);
  const active = ["open", "assigned", "waiting_on_student"].includes(ticket.status);
  const mine = ticket.assignee_user_id === user?.user_id;
  const canAssignOthers = isManager || (isHead && ticket.queue === "batch_staff");

  const run = async (action: "claim" | "release" | "resolve" | "reopen" | "close", message: string) => {
    try {
      await act({ ticketId: ticket.ticket_id, action }).unwrap();
      notify.success(message);
    } catch (error) {
      notify.apiError(error);
    }
  };
  const busy = (action: string) => isLoading && originalArgs?.action === action;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {active && !mine && <Button variant="secondary" icon="user" loading={busy("claim")} onClick={() => void run("claim", "Ticket claimed")}>Claim</Button>}
      {active && canAssignOthers && <Button variant="secondary" icon="users" onClick={() => setAssigning(true)}>Assign</Button>}
      {active && mine && <Button variant="ghost" loading={busy("release")} onClick={() => void run("release", "Back in the queue")}>Release</Button>}
      {active && <Button icon="check" loading={busy("resolve")} onClick={() => void run("resolve", "Ticket resolved")}>Resolve</Button>}
      {ticket.status === "resolved" && <Button variant="secondary" icon="refresh" loading={busy("reopen")} onClick={() => void run("reopen", "Ticket reopened")}>Reopen</Button>}
      {ticket.status !== "closed" && <Button variant="secondary" loading={busy("close")} onClick={() => void run("close", "Ticket closed")}>Close</Button>}
      {assigning && <AssignDialog ticketId={ticket.ticket_id} onClose={() => setAssigning(false)} />}
    </div>
  );
}
