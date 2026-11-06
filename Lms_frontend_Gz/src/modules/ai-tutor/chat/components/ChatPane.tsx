import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useDeleteConversationMutation, useEscalateConversationMutation, useGetConversationQuery } from "@/modules/ai-tutor/chat/api/chatApi";
import { Composer } from "@/modules/ai-tutor/chat/components/Composer";
import { MessageBubble, PendingTurn } from "@/modules/ai-tutor/chat/components/MessageBubble";
import { useTutorSend } from "@/modules/ai-tutor/chat/hooks/useTutorSend";
import { Button, ConfirmDialog, EmptyState, Spinner } from "@/shared/ui";
import { AttachedCode } from "@/modules/ai-tutor/chat/components/AttachedCode";
import { tutorAttachmentStorage } from "@/core/lib/storage";

export function ChatPane({ conversationId, itemId, available }: { conversationId: string; itemId: string | null; available: boolean }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: conversation, isLoading, isError } = useGetConversationQuery(conversationId);
  const [escalate, { isLoading: escalating }] = useEscalateConversationMutation();
  const [remove] = useDeleteConversationMutation();
  const { send, sending, pendingUser, streamed } = useTutorSend(conversationId);
  const bottom = useRef<HTMLDivElement>(null);
  const [attachment, setAttachment] = useState(() => tutorAttachmentStorage.read());

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [conversation?.messages.length, streamed, pendingUser]);

  if (isLoading) return <div className="flex flex-1 items-center justify-center"><Spinner /></div>;
  if (isError || !conversation) return <EmptyState icon="alert" title="Conversation not found" />;

  const closed = conversation.status === "closed";
  const escalated = conversation.status === "escalated";
  const context = { item_id: itemId, ...(attachment ? { code: attachment.code, language: attachment.language } : {}) };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-slate-900">{conversation.title || "New conversation"}</p>
          <p className="text-xs text-slate-500">{conversation.mode === "learning" ? "Learning" : "Support"}{itemId ? " · about the lesson you have open" : ""}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon="users"
            loading={escalating}
            disabled={closed || escalated}
            onClick={async () => {
              try {
                await escalate(conversationId).unwrap();
                notify.success("Handed to a person", "Support will reply on your ticket.");
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            {escalated ? "Handed to support" : "Talk to a person"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon="trash"
            aria-label="Delete conversation"
            onClick={() =>
              confirm.ask({ title: "Delete this conversation?", description: "It is removed from your history.", confirmLabel: "Delete" }, async () => {
                try {
                  await remove(conversationId).unwrap();
                  navigate("/tutor/chat", { replace: true });
                } catch (error) {
                  notify.apiError(error);
                }
              })
            }
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-slate-50 p-4">
        {conversation.messages.length === 0 && !pendingUser && <p className="py-8 text-center text-sm text-slate-500">Ask anything about the course. Answers cite the lessons they come from.</p>}
        {conversation.messages.map((message) => <MessageBubble key={message.message_id} message={message} />)}
        {pendingUser && <PendingTurn userText={pendingUser} streamed={streamed} />}
        <div ref={bottom} />
      </div>
      {attachment && <AttachedCode attachment={attachment} onRemove={() => { tutorAttachmentStorage.clear(); setAttachment(null); }} />}
      <Composer
        disabled={!available || closed}
        sending={sending}
        showHint={Boolean(itemId)}
        onSend={(content) => void send(content, context)}
        onHint={() => void send("Give me a hint", { ...context, hint_request: true })}
      />
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
