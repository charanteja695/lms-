import { cn } from "@/core/lib/cn";
import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { useGetTicketTranscriptQuery } from "@/modules/support/agent/api/agentTicketsApi";
import { usePromoteTutorAnswerMutation } from "@/modules/support/agent/api/promoteApi";
import { Button, Card, Spinner } from "@/shared/ui";

/**
 * The AI-tutor conversation a hand-off ticket came from (support-service reads it from ai-tutor). A good tutor
 * answer can become a draft in the tutor's FAQ — for staff and support managers, whom ai-tutor lets promote.
 */
export function TranscriptCard({ ticketId }: { ticketId: string }) {
  const notify = useNotify();
  const { canPromoteToFaq } = useSupportRights();
  const { data: transcript, isLoading, error } = useGetTicketTranscriptQuery(ticketId);
  const [promote, { isLoading: promoting, originalArgs }] = usePromoteTutorAnswerMutation();

  return (
    <Card title="AI tutor conversation" description={transcript?.title}>
      {isLoading ? (
        <Spinner />
      ) : error || !transcript ? (
        <p className="text-sm text-slate-500">{error ? toApiError(error).message : "Not available."}</p>
      ) : (
        <ol className="max-h-96 space-y-2 overflow-y-auto">
          {transcript.messages.map((message) => (
            <li key={message.message_id} className={cn("rounded-lg px-3 py-2 text-sm", message.role === "user" ? "bg-slate-100 text-slate-800" : "border border-slate-200 bg-white text-slate-700")}>
              <p className="mb-1 text-xs font-medium text-slate-500">{message.role === "user" ? "Student" : "Tutor"}</p>
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
              {canPromoteToFaq && message.role === "assistant" && message.kind === "answer" && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-1"
                  loading={promoting && originalArgs?.messageId === message.message_id}
                  onClick={async () => {
                    try {
                      await promote({ messageId: message.message_id }).unwrap();
                      notify.success("Added to the tutor FAQ as a draft", "Review and publish it in AI tutor → FAQ.");
                    } catch (promoteError) {
                      notify.apiError(promoteError);
                    }
                  }}
                >
                  Add to FAQ
                </Button>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
