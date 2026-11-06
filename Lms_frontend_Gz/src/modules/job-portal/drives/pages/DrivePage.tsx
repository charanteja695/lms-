import { useState } from "react";
import { useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { formatDate } from "@/core/lib/format";
import { DriveStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { useAttachJobToDriveMutation, useFinishDriveMutation, useGetDriveQuery, useRespondToDriveMutation } from "@/modules/job-portal/drives/api/drivesApi";
import { useListEmployerJobsQuery } from "@/modules/job-portal/employer/api/employerJobsApi";
import { Button, Card, DescriptionList, EmptyState, PageHeader, PageLoader, Select } from "@/shared/ui";

export function DrivePage() {
  const { driveId = "" } = useParams();
  const notify = useNotify();
  const rights = useJobRights();
  const { data, isLoading, isError } = useGetDriveQuery(driveId, { skip: !driveId });
  const [respond, { isLoading: responding }] = useRespondToDriveMutation();
  const [attach, { isLoading: attaching }] = useAttachJobToDriveMutation();
  const [finish, { isLoading: finishing }] = useFinishDriveMutation();
  const [jobId, setJobId] = useState("");

  const canManage = rights.isHead || rights.isSuperAdmin || rights.isAdmin;
  const canAttach = rights.isEmployer || rights.isSuperAdmin || rights.isAdmin;

  const { data: jobs } = useListEmployerJobsQuery(
    { employer_org_id: data?.drive.employer_id, per_page: 100 },
    { skip: !data?.drive.employer_id }
  );

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <EmptyState icon="alert" title="Drive not found" />;
  const { drive, summary } = data;
  const run = (work: () => Promise<unknown>, message: string) => void work().then(() => notify.success(message), notify.apiError);
  const attachable = (jobs?.items ?? []).filter((j) => j.status !== "closed" && j.drive_id !== drive.drive_id);

  return (
    <>
      <PageHeader
        title={drive.title}
        description={<span className="flex items-center gap-2"><DriveStatusBadge status={drive.status} /> {drive.company_name} at {drive.institution_name}</span>}
        backTo="/jobs/drives"
        backLabel="Drives"
        actions={
          <div className="flex gap-2">
            {(rights.isEmployerAdmin || rights.isSuperAdmin || rights.isAdmin) && drive.status === "proposed" && (
              <>
                <Button variant="secondary" loading={responding} onClick={() => run(() => respond({ id: driveId, accept: false }).unwrap(), "Declined")}>Decline</Button>
                <Button loading={responding} onClick={() => run(() => respond({ id: driveId, accept: true }).unwrap(), "Accepted")}>Accept</Button>
              </>
            )}
            {canManage && (drive.status === "proposed" || drive.status === "accepted") && (
              <>
                {drive.status === "accepted" && <Button loading={finishing} onClick={() => run(() => finish({ id: driveId, action: "complete" }).unwrap(), "Drive completed")}>Mark completed</Button>}
                <Button variant="danger" loading={finishing} onClick={() => run(() => finish({ id: driveId, action: "cancel" }).unwrap(), "Drive cancelled")}>Cancel drive</Button>
              </>
            )}
          </div>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Drive Details">
          <DescriptionList
            columns={1}
            items={[
              { label: "Company", value: drive.company_name ?? "—" },
              { label: "Institution", value: drive.institution_name ?? "—" },
              { label: "Drive Date", value: formatDate(drive.drive_date) },
              { label: "Description", value: drive.description || "—" },
            ]}
          />
        </Card>
        {summary && (
          <Card title="Numbers">
            <DescriptionList columns={1} items={Object.entries(summary).filter(([, v]) => typeof v !== "object").map(([k, v]) => ({ label: k.replace(/_/g, " "), value: String(v) }))} />
          </Card>
        )}
        {canAttach && drive.status === "accepted" && (
          <Card title="Add a job to this drive" description="The job is then open only to this institution's students.">
            <div className="flex gap-2">
              <Select aria-label="Job" value={jobId} placeholder="Choose one of the company's jobs" options={attachable.map((j) => ({ value: j.job_id, label: j.title }))} onChange={(e) => setJobId(e.target.value)} />
              <Button disabled={!jobId} loading={attaching} onClick={() => run(() => attach({ id: driveId, job_id: jobId }).unwrap().then(() => setJobId("")), "Job added to the drive")}>Add</Button>
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
