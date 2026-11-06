import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { toOptions } from "@/core/lib/options";
import { RECOMMENDATION_LABELS } from "@/modules/ai-interview/common/labels";
import { useAddCalibrationSampleMutation, type ScreeningDetail } from "@/modules/ai-interview/screening/api/screeningApi";
import { Button, Field, Input, Modal, Select } from "@/shared/ui";

/** Your own 1–5 scores for this transcript, to measure the AI against (the plan's Calibration card runs the comparison). */
export function CalibrationSampleDialog({ interview, onClose }: { interview: ScreeningDetail; onClose: () => void }) {
  const notify = useNotify();
  const [add, { isLoading }] = useAddCalibrationSampleMutation();
  const criteria = Object.keys(interview.evaluation?.criterion_scores ?? {});
  const [scores, setScores] = useState<Record<string, string>>(Object.fromEntries(criteria.map((c) => [c, "3"])));
  const [rec, setRec] = useState("yes");

  return (
    <Modal
      open
      onClose={onClose}
      title="Add as a calibration sample"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>Cancel</Button>
          <Button
            loading={isLoading}
            onClick={() =>
              void add({ planId: interview.plan_id, turns: interview.transcript, human_scores: Object.fromEntries(Object.entries(scores).map(([k, v]) => [k, Number(v)])), human_recommendation: rec })
                .unwrap()
                .then(() => { notify.success("Sample added"); onClose(); }, notify.apiError)
            }
          >
            Add sample
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {criteria.map((c) => (
          <Field key={c} label={c.replace(/_/g, " ")}>{(p) => <Input {...p} type="number" min={1} max={5} value={scores[c]} onChange={(e) => setScores({ ...scores, [c]: e.target.value })} />}</Field>
        ))}
        <Field label="Your recommendation" className="sm:col-span-2">{(p) => <Select {...p} value={rec} options={toOptions(RECOMMENDATION_LABELS)} onChange={(e) => setRec(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
