import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useRateTutorMessageMutation } from "@/modules/ai-tutor/chat/api/chatApi";
import type { Rating } from "@/modules/ai-tutor/common/types";
import { Button, Textarea } from "@/shared/ui";

/** Thumbs up/down on an answer; a thumbs-down may say why. Re-rating replaces the earlier rating server-side. */
export function MessageFeedback({ messageId }: { messageId: string }) {
  const notify = useNotify();
  const [rate, { isLoading }] = useRateTutorMessageMutation();
  const [rated, setRated] = useState<Rating | null>(null);
  const [commenting, setCommenting] = useState(false);
  const [comment, setComment] = useState("");

  const submit = async (rating: Rating, text?: string) => {
    try {
      await rate({ messageId, rating, comment: text || undefined }).unwrap();
      setRated(rating);
      setCommenting(false);
      if (rating === "down") notify.success("Thanks — this helps improve the tutor");
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center gap-1 text-xs text-slate-500">
        <span>Helpful?</span>
        <Button variant={rated === "up" ? "secondary" : "ghost"} size="sm" disabled={isLoading} onClick={() => void submit("up")}>
          Yes
        </Button>
        <Button variant={rated === "down" ? "secondary" : "ghost"} size="sm" disabled={isLoading} onClick={() => setCommenting(true)}>
          No
        </Button>
      </div>
      {commenting && (
        <div className="space-y-2">
          <Textarea value={comment} rows={2} maxLength={500} placeholder="What was wrong? (optional)" onChange={(event) => setComment(event.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" loading={isLoading} onClick={() => void submit("down", comment.trim())}>
              Send
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setCommenting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
