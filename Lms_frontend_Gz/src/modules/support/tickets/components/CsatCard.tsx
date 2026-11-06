import { useState } from "react";

import { cn } from "@/core/lib/cn";
import { useNotify } from "@/core/hooks/useNotify";
import { useRateMyTicketMutation } from "@/modules/support/tickets/api/myTicketsApi";
import { Button, Card, Textarea } from "@/shared/ui";

/** Shown once a ticket is resolved and not yet rated (the server allows one rating, 1–5). */
export function CsatCard({ ticketId }: { ticketId: string }) {
  const notify = useNotify();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [rate, { isLoading }] = useRateMyTicketMutation();

  return (
    <Card title="How did we do?">
      <div className="space-y-3">
        <div className="flex gap-2" role="radiogroup" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={rating === value}
              onClick={() => setRating(value)}
              className={cn("h-10 w-10 rounded-lg border text-sm font-semibold", rating >= value ? "border-brand-600 bg-brand-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-brand-300")}
            >
              {value}
            </button>
          ))}
        </div>
        <Textarea aria-label="Comment" rows={2} maxLength={500} placeholder="Anything to add? (optional)" value={comment} onChange={(event) => setComment(event.target.value)} />
        <div className="flex justify-end">
          <Button
            loading={isLoading}
            disabled={rating === 0}
            onClick={async () => {
              try {
                await rate({ ticketId, rating, comment: comment.trim() || undefined }).unwrap();
                notify.success("Thanks for the feedback");
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Send rating
          </Button>
        </div>
      </div>
    </Card>
  );
}
