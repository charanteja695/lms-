import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCompanyOptions, useInstitutionDirectoryOptions } from "@/modules/job-portal/common/api/directoryApi";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { useCreateDriveMutation } from "@/modules/job-portal/drives/api/drivesApi";
import { useListEmployerJobsQuery } from "@/modules/job-portal/employer/api/employerJobsApi";
import { Button, EntityPicker, Field, Input, Modal, Select, Textarea } from "@/shared/ui";

const STATUS_OPTIONS = [
  { value: "proposed", label: "Proposed (Pending Acceptance)" },
  { value: "accepted", label: "Accepted (Active Drive)" },
];

/** Admin or Head creates a placement drive with company, institution, jobs, and schedule. */
export function NewDriveDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const notify = useNotify();
  const rights = useJobRights();
  const [create, { isLoading }] = useCreateDriveMutation();

  const [company, setCompany] = useState({ id: "", label: "" });
  const [institution, setInstitution] = useState({ id: "", label: "" });
  const [title, setTitle] = useState("");
  const [driveDate, setDriveDate] = useState("");
  const [deadlineDate, setDeadlineDate] = useState("");
  const [status, setStatus] = useState<string>("proposed");
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([]);
  const [description, setDescription] = useState("");

  const isPlatformAdmin = rights.isSuperAdmin || rights.isAdmin;

  // Query jobs for the selected company to allow associating them
  const { data: jobsData } = useListEmployerJobsQuery(
    { employer_org_id: company.id, per_page: 50 },
    { skip: !company.id }
  );

  const availableJobs = jobsData?.items ?? [];

  const toggleJob = (jobId: string) => {
    setSelectedJobIds((prev) =>
      prev.includes(jobId) ? prev.filter((id) => id !== jobId) : [...prev, jobId]
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Create Placement Drive"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            loading={isLoading}
            disabled={!company.id || !title.trim()}
            onClick={async () => {
              try {
                const created = await create({
                  employer_id: company.id,
                  institution_id: isPlatformAdmin && institution.id ? institution.id : undefined,
                  title: title.trim(),
                  description: description.trim() || undefined,
                  drive_date: driveDate || undefined,
                  deadline_date: deadlineDate || undefined,
                  status,
                  job_ids: selectedJobIds.length > 0 ? selectedJobIds : undefined,
                }).unwrap();
                notify.success(
                  status === "accepted" ? "Placement Drive Created" : "Drive Proposed",
                  status === "accepted"
                    ? "Placement drive is active and open for applications."
                    : "Invitation sent to the hiring company."
                );
                onCreated(created.drive.drive_id);
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Create Placement Drive
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Drive Name / Title" required>
          {(p) => (
            <Input
              {...p}
              maxLength={160}
              value={title}
              placeholder="e.g. Campus Recruitment Drive 2026"
              onChange={(e) => setTitle(e.target.value)}
            />
          )}
        </Field>

        <EntityPicker
          label="Hiring Company"
          required
          value={company.id}
          selectedLabel={company.label}
          useOptions={useCompanyOptions}
          hint="Select verified partner company."
          onChange={(id, label) => {
            setCompany({ id, label });
            setSelectedJobIds([]);
          }}
        />

        {isPlatformAdmin && (
          <EntityPicker
            label="Target Institution"
            value={institution.id}
            selectedLabel={institution.label}
            useOptions={useInstitutionDirectoryOptions}
            hint="Leave blank to use default primary institution."
            onChange={(id, label) => setInstitution({ id, label })}
          />
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Drive Date">
            {(p) => <Input {...p} type="date" value={driveDate} onChange={(e) => setDriveDate(e.target.value)} />}
          </Field>
          <Field label="Registration Deadline">
            {(p) => (
              <Input
                {...p}
                type="date"
                value={deadlineDate}
                onChange={(e) => setDeadlineDate(e.target.value)}
              />
            )}
          </Field>
        </div>

        <Field label="Status">
          {() => (
            <Select
              value={status}
              options={STATUS_OPTIONS}
              onChange={(e) => setStatus(e.target.value)}
            />
          )}
        </Field>

        {company.id && availableJobs.length > 0 && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Associated Jobs ({availableJobs.length} available)
            </label>
            <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100 p-1 bg-slate-50/50">
              {availableJobs.map((j) => (
                <label
                  key={j.job_id}
                  className="flex items-center gap-2 p-2 rounded hover:bg-white text-xs cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                    checked={selectedJobIds.includes(j.job_id)}
                    onChange={() => toggleJob(j.job_id)}
                  />
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900 truncate">{j.title}</p>
                    <p className="text-[11px] text-slate-500 capitalize">{j.employment_type} · {j.location_type}</p>
                  </div>
                </label>
              ))}
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Selected jobs will be restricted to students eligible for this drive.
            </p>
          </div>
        )}

        <Field label="Description">
          {(p) => (
            <Textarea
              {...p}
              rows={3}
              maxLength={2000}
              placeholder="Provide drive overview, process details, or instructions..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}
