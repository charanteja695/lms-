import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { EMPLOYMENT_LABELS } from "@/modules/job-portal/common/labels";
import type { EmploymentType } from "@/modules/job-portal/common/types";
import { useSaveJobPreferencesMutation } from "@/modules/job-portal/board/api/boardApi";
import type { JobPreferences } from "@/modules/job-portal/board/types";
import { Button, Checkbox, Field, Input, Modal } from "@/shared/ui";

const list = (value: string) => value.split(",").map((part) => part.trim()).filter(Boolean);

/** What recommendations aim for; changing them re-scores (server-side). Off "open to work" = no recommendations. */
export function PreferencesDialog({ current, onClose }: { current: JobPreferences; onClose: () => void }) {
  const notify = useNotify();
  const [save, { isLoading }] = useSaveJobPreferencesMutation();
  const [openToWork, setOpenToWork] = useState(current.open_to_work);
  const [roles, setRoles] = useState(current.roles.join(", "));
  const [locations, setLocations] = useState(current.locations.join(", "));
  const [remote, setRemote] = useState(current.open_to_remote);
  const [minCtc, setMinCtc] = useState(current.min_ctc ? String(current.min_ctc / 100_000) : "");
  const [types, setTypes] = useState<EmploymentType[]>(current.employment_types);

  return (
    <Modal
      open
      onClose={onClose}
      title="Job preferences"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>Cancel</Button>
          <Button
            loading={isLoading}
            onClick={async () => {
              try {
                await save({ open_to_work: openToWork, roles: list(roles), locations: list(locations), open_to_remote: remote, min_ctc: minCtc ? Math.round(Number(minCtc) * 100_000) : null, employment_types: types }).unwrap();
                notify.success("Preferences saved", "Recommendations are being refreshed.");
                onClose();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Checkbox label="I'm open to work" description="While this is off you get no recommendations." checked={openToWork} onChange={(e) => setOpenToWork(e.target.checked)} />
        <Field label="Roles" hint="Comma separated.">{(props) => <Input {...props} value={roles} onChange={(e) => setRoles(e.target.value)} />}</Field>
        <Field label="Locations" hint="Comma separated.">{(props) => <Input {...props} value={locations} onChange={(e) => setLocations(e.target.value)} />}</Field>
        <Checkbox label="Open to remote" checked={remote} onChange={(e) => setRemote(e.target.checked)} />
        <Field label="Minimum CTC (lakhs per year)">{(props) => <Input {...props} type="number" min={0} step="0.5" value={minCtc} onChange={(e) => setMinCtc(e.target.value)} />}</Field>
        <div className="flex flex-wrap gap-4">
          {(Object.keys(EMPLOYMENT_LABELS) as EmploymentType[]).map((type) => (
            <Checkbox key={type} label={EMPLOYMENT_LABELS[type]} checked={types.includes(type)} onChange={(e) => setTypes(e.target.checked ? [...types, type] : types.filter((t) => t !== type))} />
          ))}
        </div>
      </div>
    </Modal>
  );
}
