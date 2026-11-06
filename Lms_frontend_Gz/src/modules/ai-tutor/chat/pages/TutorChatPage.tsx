import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { useGetTutorAvailabilityQuery } from "@/modules/ai-tutor/chat/api/chatApi";
import { ChatPane } from "@/modules/ai-tutor/chat/components/ChatPane";
import { ConversationList } from "@/modules/ai-tutor/chat/components/ConversationList";
import { NewConversationDialog } from "@/modules/ai-tutor/chat/components/NewConversationDialog";
import { Alert, Button, EmptyState, PageHeader } from "@/shared/ui";

/**
 * `/tutor/chat[/:conversationId]`. Opened from the course player with `?course=<id>&item=<lesson id>`: the
 * new-conversation dialog opens on that course, and the lesson travels with every message as context.
 */
export function TutorChatPage() {
  const { conversationId } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const courseParam = search.get("course");
  const itemId = search.get("item");
  const [creating, setCreating] = useState(Boolean(courseParam) && !conversationId);
  const { data: availability } = useGetTutorAvailabilityQuery();
  const available = availability?.enabled ?? true;

  return (
    <>
      <PageHeader
        title="AI tutor"
        description="Answers grounded in your course, with hints before solutions."
        actions={
          <Button variant="secondary" icon="helpCircle" onClick={() => navigate("/tutor/faq")}>
            FAQ
          </Button>
        }
      />
      {!available && (
        <Alert tone="warning" title="The tutor is switched off right now" className="mb-4">
          {availability?.reason === "GRADED_TEST_IN_PROGRESS" ? "You have a graded test in progress." : availability?.reason}
          {availability?.blocked_until && ` Available again after ${formatDateTime(availability.blocked_until)}.`}
        </Alert>
      )}
      <div className="flex h-[calc(100vh-14rem)] min-h-[28rem] flex-col overflow-hidden rounded-xl border border-slate-200 lg:flex-row">
        <ConversationList activeId={conversationId} onNew={() => setCreating(true)} />
        {conversationId ? (
          <ChatPane key={conversationId} conversationId={conversationId} itemId={itemId} available={available} />
        ) : (
          <div className="flex flex-1 items-center justify-center bg-slate-50">
            <EmptyState icon="helpCircle" title="Pick a conversation or start a new one" action={<Button icon="plus" onClick={() => setCreating(true)}>New conversation</Button>} />
          </div>
        )}
      </div>
      {creating && (
        <NewConversationDialog
          open={creating}
          initialCourseId={courseParam}
          onClose={() => setCreating(false)}
          onCreated={(conversation) => {
            setCreating(false);
            navigate(`/tutor/chat/${conversation.conversation_id}${itemId ? `?item=${itemId}` : ""}`);
          }}
        />
      )}
    </>
  );
}
