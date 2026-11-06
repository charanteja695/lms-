import { Navigate, useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useListParams } from "@/core/hooks/useListParams";
import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { formatDate } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { JobStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { EMPLOYMENT_LABELS, JOB_STATUS_LABELS, LOCATION_TYPE_LABELS } from "@/modules/job-portal/common/labels";
import { useListEmployersQuery } from "@/modules/user-management/employers/api/employersApi";
import type { JobStatus } from "@/modules/job-portal/common/types";
import {
  useCloseJobMutation,
  useDeleteEmployerJobMutation,
  useGetMyCompanyQuery,
  useJobActionMutation,
  useListEmployerJobsQuery,
} from "@/modules/job-portal/employer/api/employerJobsApi";
import type { EmployerJob, JobAction } from "@/modules/job-portal/employer/types";
import {
  Alert,
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  EmptyState,
  FilterRow,
  FilterSelect,
  FilterText,
  PageHeader,
  Pagination,
  type Column,
} from "@/shared/ui";

export function EmployerJobsPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { isCareersManager, isEmployer, isStudent } = useJobRights();
  const { permissions } = usePermissions();
  const isAdmin = permissions.role === "super_admin" || permissions.role === "admin" || isCareersManager;

  if (isStudent || permissions.role === "student") {
    return <Navigate to="/jobs/board" replace />;
  }

  const { data: company } = useGetMyCompanyQuery(undefined, { skip: !isEmployer });
  const { params, update } = useListParams<{ q: string; status: string | undefined; employer_org_id: string | undefined }>({
    page: 1,
    per_page: 20,
  });

  const { data: employersData } = useListEmployersQuery(
    { page: 1, per_page: 100 },
    { skip: !isAdmin }
  );

  const companyOptions = [
    { value: "", label: "All Companies" },
    ...(employersData?.items ?? []).map((emp) => ({
      value: emp.organization_id,
      label: emp.name,
    })),
  ];

  const apiParams = {
    ...params,
    status: params.status as JobStatus | undefined,
    employer_org_id: isAdmin ? params.employer_org_id || undefined : undefined,
  };

  const { data, isFetching } = useListEmployerJobsQuery(apiParams);
  const [act] = useJobActionMutation();
  const [close] = useCloseJobMutation();
  const [deleteJob] = useDeleteEmployerJobMutation();

  const handleAction = async (jobId: string, action: JobAction, message: string) => {
    try {
      await act({ jobId, action }).unwrap();
      notify.success(message);
    } catch (error) {
      const err = toApiError(error);
      notify.error(err.message, err.details.map((d) => d.message).join(" ") || undefined);
    }
  };

  const handleClose = (item: EmployerJob) => {
    confirm.ask(
      {
        title: `Close "${item.title}"?`,
        description: "Applications will be closed. Existing candidates will remain in the pipeline.",
        confirmLabel: "Close Job",
        withReason: true,
      },
      async (reason) => {
        try {
          await close({ jobId: item.job_id, reason: reason || "Closed by administrator" }).unwrap();
          notify.success("Job closed successfully");
        } catch (error) {
          const err = toApiError(error);
          notify.error(err.message, err.details.map((d) => d.message).join(" ") || undefined);
        }
      }
    );
  };

  const handleDelete = (item: EmployerJob) => {
    confirm.ask(
      {
        title: `Delete "${item.title}"?`,
        description: "Are you sure you want to permanently delete this job posting? This action cannot be undone.",
        confirmLabel: "Delete Job",
      },
      async () => {
        try {
          await deleteJob(item.job_id).unwrap();
          notify.success("Job deleted successfully");
        } catch (error) {
          const err = toApiError(error);
          notify.error(err.message, err.details.map((d) => d.message).join(" ") || undefined);
        }
      }
    );
  };

  const columns: Column<EmployerJob>[] = [
    {
      key: "title",
      header: "Job & Company",
      className: "min-w-[220px]",
      render: (item) => (
        <div className="min-w-0">
          <button
            type="button"
            className="text-left font-semibold text-slate-900 hover:text-brand-600 hover:underline block truncate"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/jobs/employer/${item.job_id}`);
            }}
          >
            {item.title}
          </button>
          <p className="text-xs text-slate-500 mt-0.5 truncate">
            {[item.company_name, EMPLOYMENT_LABELS[item.employment_type]].filter(Boolean).join(" · ")}
          </p>
        </div>
      ),
    },
    {
      key: "location",
      header: "Work Mode & Location",
      className: "min-w-[160px]",
      hideOnMobile: true,
      render: (item) => (
        <div className="text-xs">
          <span className="font-medium text-slate-700">{LOCATION_TYPE_LABELS[item.location_type]}</span>
          {item.locations && item.locations.length > 0 && item.location_type !== "remote" && (
            <p className="text-slate-500 truncate max-w-[180px]">{item.locations.join(", ")}</p>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      className: "min-w-[120px]",
      render: (item) => <JobStatusBadge status={item.status} />,
    },
    {
      key: "applications",
      header: "Applicants",
      className: "min-w-[130px]",
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/jobs/employer/${item.job_id}?tab=applicants`);
          }}
          className="group inline-flex items-center gap-1.5 text-left hover:underline focus:outline-none"
          title="View Applicants"
        >
          <span className="font-semibold text-slate-900 group-hover:text-brand-600">
            {item.applications}
          </span>
          <span className="text-xs text-slate-500 group-hover:text-brand-600">
            {item.applications === 1 ? "applicant" : "applicants"}
          </span>
        </button>
      ),
    },
    {
      key: "deadline",
      header: "Deadline",
      className: "min-w-[130px]",
      hideOnMobile: true,
      render: (item) => (
        <div className="text-xs text-slate-600">
          {item.deadline_at ? formatDate(item.deadline_at) : <span className="text-slate-400">None</span>}
        </div>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "min-w-[340px] text-right whitespace-nowrap",
      render: (item) => (
        <div className="inline-flex items-center justify-end gap-1.5 whitespace-nowrap">
          <Button
            variant={item.applications > 0 ? "secondary" : "ghost"}
            size="sm"
            onClick={() => navigate(`/jobs/employer/${item.job_id}${item.applications > 0 ? "?tab=applicants" : ""}`)}
          >
            {item.applications > 0 ? `Applicants (${item.applications})` : "View"}
          </Button>

          {(item.status === "draft" || item.status === "open" || item.status === "paused") && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`/jobs/employer/${item.job_id}/edit`)}
            >
              Edit
            </Button>
          )}

          {item.status === "draft" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAction(item.job_id, "submit", "Job published successfully!")}
            >
              Publish
            </Button>
          )}

          {item.status === "open" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAction(item.job_id, "pause", "Job paused (unpublished).")}
            >
              Pause
            </Button>
          )}

          {item.status === "paused" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAction(item.job_id, "resume", "Job reopened and published.")}
            >
              Resume
            </Button>
          )}

          {(item.status === "open" || item.status === "paused") && (
            <Button
              variant="ghost"
              size="sm"
              className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
              onClick={() => handleClose(item)}
            >
              Close
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            className="text-red-600 hover:text-red-700 hover:bg-red-50"
            onClick={() => handleDelete(item)}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  const newJob = "/jobs/employer/new";

  return (
    <>
      <PageHeader
        title="Job Management"
        description={
          isAdmin
            ? "Create, publish, edit, and track job postings across all partner companies."
            : company?.company_name || "Manage company job postings."
        }
        actions={
          <Button variant="primary" icon="plus" onClick={() => navigate(newJob)}>
            Create Job
          </Button>
        }
      />
      <JobTabs />

      {company && company.status !== "verified" && (
        <Alert tone="warning" className="mb-4" title="Company Not Verified Yet">
          Drafts can be created, but job postings cannot be published until the company profile is verified.
        </Alert>
      )}

      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterText
            label="Search"
            placeholder="Search by title, role, or keywords..."
            value={apiParams.q}
            onChange={(value) => update({ q: value })}
          />
          <FilterSelect
            label="Status"
            value={apiParams.status}
            options={toOptions(JOB_STATUS_LABELS)}
            onChange={(value) => update({ status: value })}
          />
          {isAdmin && (
            <FilterSelect
              label="Company"
              value={apiParams.employer_org_id}
              options={companyOptions}
              onChange={(value) => update({ employer_org_id: value })}
            />
          )}
        </FilterRow>

        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(item) => item.job_id}
          loading={isFetching}
          onRowClick={(item) => navigate(`/jobs/employer/${item.job_id}`)}
          empty={
            <EmptyState
              icon="briefcase"
              title="No jobs found"
              description={
                isAdmin
                  ? "No job openings match the selected filters. Click '+ Create Job' to post an opening."
                  : "Post your first job opening to start receiving student applications."
              }
              action={
                <Button variant="primary" icon="plus" onClick={() => navigate(newJob)}>
                  Create Job
                </Button>
              }
            />
          }
        />
        <Pagination
          pageContext={data?.pageContext}
          disabled={isFetching}
          onPageChange={(next) => update({ page: next })}
          onPerPageChange={(next) => update({ per_page: next })}
        />
      </Card>

      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
