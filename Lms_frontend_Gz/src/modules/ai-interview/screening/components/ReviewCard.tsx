import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { toOptions } from "@/core/lib/options";
import { RecommendationBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { RECOMMENDATION_LABELS } from "@/modules/ai-interview/common/labels";
import { useReviewInterviewMutation, type ScreeningDetail } from "@/modules/ai-interview/screening/api/screeningApi";
import { Button, Card, Checkbox, Field, Select, Textarea } from "@/shared/ui";

/** Confirm the AI's recommendation or override it (with a note), and choose whether the candidate may see their feedback. */
export function ReviewCard({ interview }: { interview: ScreeningDetail }) {
  const notify = useNotify();
  const [review, { isLoading }] = useReviewInterviewMutation();
  const [override, setOverride] = useState("");
  const [note, setNote] = useState("");
  const [release, setRelease] = useState(true);

  if (interview.reviewed_at) {
    return (
      <Card title="Your team's review">
        <p className="flex items-center gap-2 text-sm">Final <RecommendationBadge value={interview.final_recommendation} /></p>
        {interview.review_note && <p className="mt-2 text-sm text-slate-700">{interview.review_note}</p>}
        <p className="mt-2 text-xs text-slate-500">{interview.feedback_released ? "Feedback released to the candidate." : "Feedback not released."}</p>
      </Card>
    );
  }

  return (
    <Card title="Review">
      <div className="space-y-3">
        <Field label="Recommendation" hint="Leave as is to confirm the AI's.">
          {(p) => <Select {...p} value={override} placeholder="Confirm the AI's recommendation" options={toOptions(RECOMMENDATION_LABELS)} onChange={(e) => setOverride(e.target.value)} />}
        </Field>
        <Field label="Note" required={Boolean(override)} hint={override ? "Required when you override." : "Optional."}>{(p) => <Textarea {...p} rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
        <Checkbox label="Release feedback to the candidate" description="Their report shows scores and what to improve — never the recommendation." checked={release} onChange={(e) => setRelease(e.target.checked)} />
        <div className="flex justify-end">
          <Button
            loading={isLoading}
            disabled={!interview.evaluation || (Boolean(override) && !note.trim())}
            onClick={() => void review({ id: interview.interview_id, recommendation: override || undefined, note: note.trim() || undefined, release_feedback: release }).unwrap().then(() => notify.success("Review saved"), notify.apiError)}
          >
            Save review
          </Button>
        </div>
      </div>
    </Card>
  );
}
