import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { useParams } from "react-router-dom";

import { env } from "@/core/config/env";
import { MessageThread } from "@/modules/support/common/components/MessageThread";
import { PriorityBadge, TicketStatusBadge } from "@/modules/support/common/components/TicketBadges";
import { useGetAgentTicketQuery } from "@/modules/support/agent/api/agentTicketsApi";
import { AgentReplyBox } from "@/modules/support/agent/components/detail/AgentReplyBox";
import { TicketActions } from "@/modules/support/agent/components/detail/TicketActions";
import { TicketEventsCard } from "@/modules/support/agent/components/detail/TicketEventsCard";
import { TicketPropertiesCard } from "@/modules/support/agent/components/detail/TicketPropertiesCard";
import { TranscriptCard } from "@/modules/support/agent/components/detail/TranscriptCard";
import { Card, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function AgentTicketPage() {
  const { ticketId = "" } = useParams();
  const { canAnswer } = useSupportRights();
  const { data, isLoading, isError } = useGetAgentTicketQuery(ticketId, { skip: !ticketId, pollingInterval: env.liveRefreshMs, skipPollingIfUnfocused: true });

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <EmptyState icon="alert" title="Ticket not found" description="It may be in a queue you don't handle." />;
  const { ticket } = data;

  return (
    <>
      <PageHeader
        title={ticket.subject}
        description={
          <span className="flex items-center gap-2">
            <TicketStatusBadge status={ticket.status} /> <PriorityBadge priority={ticket.priority} />
          </span>
        }
        backTo="/support/queue"
        backLabel="Queue"
        actions={canAnswer ? <TicketActions ticket={ticket} /> : undefined}
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          <Card title="Conversation">
            <MessageThread messages={data.messages} requesterName={data.requester_name} ticketPath={`/agent/tickets/${ticketId}`} />
          </Card>
          {ticket.status !== "closed" && canAnswer && <AgentReplyBox ticketId={ticketId} />}
        </div>
        <div className="space-y-4">
          <TicketPropertiesCard detail={data} />
          {ticket.source === "ai-tutor" && <TranscriptCard ticketId={ticketId} />}
          <TicketEventsCard ticketId={ticketId} />
        </div>
      </div>
    </>
  );
}
