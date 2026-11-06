import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { formatRelative } from "@/core/lib/format";
import { useListConversationsQuery } from "@/modules/ai-tutor/chat/api/chatApi";
import { Button, Spinner } from "@/shared/ui";

export function ConversationList({ activeId, onNew }: { activeId: string | undefined; onNew: () => void }) {
  const { data, isLoading } = useListConversationsQuery({ per_page: 50 });
  const conversations = data?.items ?? [];

  return (
    <aside className="flex min-h-0 flex-col border-b border-slate-200 bg-white lg:w-72 lg:border-b-0 lg:border-r">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 p-3">
        <p className="text-sm font-semibold text-slate-900">Conversations</p>
        <Button size="sm" icon="plus" onClick={onNew}>
          New
        </Button>
      </div>
      <div className="max-h-48 overflow-y-auto lg:max-h-none lg:flex-1">
        {isLoading && <div className="p-4"><Spinner /></div>}
        {!isLoading && conversations.length === 0 && <p className="p-4 text-sm text-slate-500">No conversations yet.</p>}
        {conversations.map((conversation) => (
          <Link
            key={conversation.conversation_id}
            to={`/tutor/chat/${conversation.conversation_id}`}
            className={cn("block border-b border-slate-100 px-3 py-2.5 hover:bg-slate-50", conversation.conversation_id === activeId && "bg-brand-50")}
          >
            <p className="truncate text-sm text-slate-800">{conversation.title || "New conversation"}</p>
            <p className="text-xs text-slate-500">
              {conversation.mode === "learning" ? "Learning" : "Support"} · {formatRelative(conversation.last_message_at ?? conversation.created_at)}
            </p>
          </Link>
        ))}
      </div>
    </aside>
  );
}
