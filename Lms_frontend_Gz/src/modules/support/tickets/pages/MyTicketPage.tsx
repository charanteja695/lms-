import { useParams } from "react-router-dom";

import { env } from "@/core/config/env";
import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { CATEGORY_LABELS } from "@/modules/support/common/labels";
import { MessageThread } from "@/modules/support/common/components/MessageThread";
import { TicketStatusBadge } from "@/modules/support/common/components/TicketBadges";
import { useCloseMyTicketMutation, useGetMyTicketQuery } from "@/modules/support/tickets/api/myTicketsApi";
import { CsatCard } from "@/modules/support/tickets/components/CsatCard";
import { MyReplyBox } from "@/modules/support/tickets/components/MyReplyBox";
import { Alert, Button, Card, ConfirmDialog, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function MyTicketPage() {
  const { ticketId = "" } = useParams();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data, isLoading, isError } = useGetMyTicketQuery(ticketId, { skip: !ticketId, pollingInterval: env.liveRefreshMs, skipPollingIfUnfocused: true });
  const [close] = useCloseMyTicketMutation();

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <EmptyState icon="alert" title="Ticket not found" />;
  const { ticket } = data;
  const closed = ticket.status === "closed";

  return (
    <>
      <PageHeader
        title={ticket.subject}
        description={CATEGORY_LABELS[ticket.category]}
        backTo="/support/my-tickets"
        backLabel="My tickets"
        actions={
          <div className="flex items-center gap-2">
            <TicketStatusBadge status={ticket.status} forStudent />
            {!closed && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  confirm.ask({ title: "Close this ticket?", description: "Do this when your problem is solved. A closed ticket can't be reopened.", confirmLabel: "Close ticket", tone: "primary" }, async () => {
                    try {
                      await close(ticketId).unwrap();
                    } catch (error) {
                      notify.apiError(error);
                    }
                  })
                }
              >
                Close ticket
              </Button>
            )}
          </div>
        }
      />
      <div className="space-y-4">
        {ticket.status === "resolved" && ticket.csat_rating == null && <CsatCard ticketId={ticketId} />}
        {ticket.status === "resolved" && <Alert tone="info">Marked resolved. Replying reopens it, within the reopen window.</Alert>}
        <Card title="Conversation">
          <MessageThread messages={data.messages} requesterName="You" ticketPath={`/tickets/${ticketId}`} />
        </Card>
        {!closed && <MyReplyBox ticketId={ticketId} />}
      </div>
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
