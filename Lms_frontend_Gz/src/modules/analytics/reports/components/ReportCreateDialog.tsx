import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { DASHBOARD_BY_KEY } from "@/modules/analytics/common/dashboards";
import { useAnalyticsRights } from "@/modules/analytics/common/hooks/useAnalyticsRights";
import type { DashboardKey, ReportFormat, ReportFrequency } from "@/modules/analytics/common/types";
import { FORMAT_LABELS, FREQUENCY_LABELS } from "@/modules/analytics/reports/labels";
import { useCreateReportMutation } from "@/modules/analytics/reports/api/reportsApi";
import { useAnyEmployerOptions, useAnyInstitutionOptions } from "@/modules/user-management/common/hooks/useDirectoryOptions";
import { toOptions } from "@/core/lib/options";
import { Button, EntityPicker, Field, Input, Modal, Select } from "@/shared/ui";

/** Save one of the person's own dashboards to run on a schedule. Members' reports always cover their own organisation. */
export function ReportCreateDialog({ onClose }: { onClose: () => void }) {
  const notify = useNotify();
  const { dashboards } = useAnalyticsRights();
  const [create, { isLoading }] = useCreateReportMutation();
  const [name, setName] = useState("");
  const [key, setKey] = useState<DashboardKey>(dashboards[0]?.key ?? "content");
  const [frequency, setFrequency] = useState<ReportFrequency>("weekly");
  const [format, setFormat] = useState<ReportFormat>("csv");
  const [org, setOrg] = useState({ id: "", label: "" });
  const [employer, setEmployer] = useState({ id: "", label: "" });
  const access = dashboards.find((d) => d.key === key);
  const platform = Boolean(access?.platform);
  const filters = platform ? { organization_id: org.id || undefined, employer_id: key === "hiring" ? employer.id || undefined : undefined } : access?.fixed ?? {};
  const missingOrg = platform && key === "institution" && !org.id;

  const submit = () =>
    void create({ name: name.trim(), dashboard: key, filters, frequency, format })
      .unwrap()
      .then(() => { notify.success("Report scheduled"); onClose(); }, notify.apiError);

  return (
    <Modal
      open
      onClose={onClose}
      title="Schedule a report"
      description="Runs over the last 7 days each time; download past runs from the report."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>Cancel</Button>
          <Button loading={isLoading} disabled={name.trim().length < 3 || missingOrg} onClick={submit}>Schedule</Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Name" required>{(p) => <Input {...p} maxLength={160} value={name} onChange={(e) => setName(e.target.value)} placeholder="Weekly placements" />}</Field>
        <Field label="Dashboard" required>
          {(p) => <Select {...p} value={key} options={dashboards.map((d) => ({ value: d.key, label: DASHBOARD_BY_KEY[d.key].label }))} onChange={(e) => setKey(e.target.value as DashboardKey)} />}
        </Field>
        {platform && key !== "content" && key !== "exam_integrity" && (
          <EntityPicker label="Institution" required={key === "institution"} placeholder={key === "institution" ? "Choose an institution" : "All institutions"} value={org.id} selectedLabel={org.label} useOptions={useAnyInstitutionOptions} onChange={(id, label) => setOrg({ id, label })} />
        )}
        {platform && key === "hiring" && <EntityPicker label="Company" placeholder="All companies" value={employer.id} selectedLabel={employer.label} useOptions={useAnyEmployerOptions} onChange={(id, label) => setEmployer({ id, label })} />}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Frequency">{(p) => <Select {...p} value={frequency} options={toOptions(FREQUENCY_LABELS)} onChange={(e) => setFrequency(e.target.value as ReportFrequency)} />}</Field>
          <Field label="Format">{(p) => <Select {...p} value={format} options={toOptions(FORMAT_LABELS)} onChange={(e) => setFormat(e.target.value as ReportFormat)} />}</Field>
        </div>
      </div>
    </Modal>
  );
}
