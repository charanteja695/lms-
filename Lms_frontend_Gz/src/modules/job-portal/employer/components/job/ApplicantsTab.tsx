import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import { formatDate } from "@/core/lib/format";
import { ApplicationStatusBadge, MatchBadge } from "@/modules/job-portal/common/components/JobBadges";
import { TERMINAL_STATUSES } from "@/modules/job-portal/common/terminal";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";
import {
  useGetFunnelQuery,
  useGetRankingQuery,
  useListApplicantsQuery,
  useShortlistApplicantsMutation,
} from "@/modules/job-portal/employer/api/pipelineApi";
import { AiRankingBanner } from "@/modules/job-portal/employer/components/job/AiRankingBanner";
import { RejectDialog } from "@/modules/job-portal/employer/components/job/RejectDialog";
import type { Applicant } from "@/modules/job-portal/employer/pipelineTypes";
import {
  Button,
  Checkbox,
  DataTable,
  EmptyState,
  FilterRow,
  FilterSelect,
  FilterText,
  type Column,
} from "@/shared/ui";

const SUGGESTION: Record<string, { label: string; tone: string }> = {
  shortlist: { label: "Shortlist", tone: "bg-brand-50 text-brand-800" },
  review: { label: "Review", tone: "bg-amber-50 text-amber-800" },
  reject: { label: "Not now", tone: "bg-slate-100 text-slate-600" },
};

const SORT_OPTIONS = [
  { value: "recent", label: "Date Applied (Newest first)" },
  { value: "match", label: "Match Score (Highest first)" },
  { value: "screen", label: "AI Screen Score (Highest first)" },
];

/** Applicants by this job's stages (tabs from the server), the AI's suggestion and reasons on each row, and decisions made by a person. */
export function ApplicantsTab({ jobId }: { jobId: string }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: funnel } = useGetFunnelQuery(jobId);
  const stages = funnel?.stages ?? [];

  const allStages: { key: string; label: string; statuses?: ApplicationStatus[]; count: number }[] = [
    { key: "all", label: "All Applicants", count: funnel?.total ?? 0, statuses: undefined },
    ...stages,
  ];

  const [stageKey, setStageKey] = useState<string>("all");
  const stage = allStages.find((s) => s.key === stageKey) ?? allStages[0];

  const [q, setQ] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [sortBy, setSortBy] = useState<"recent" | "match" | "screen">("recent");

  // Determine query status parameter:
  // If specific statusFilter dropdown is set, use that; otherwise use stage tab's statuses (undefined if "all")
  const queryStatus = statusFilter ? [statusFilter as ApplicationStatus] : stage?.statuses;

  const { data, isFetching } = useListApplicantsQuery({
    jobId,
    status: queryStatus,
    q,
    sort: sortBy,
    per_page: 100,
  });

  const isNew = stage?.key === "new";
  const { data: ranking } = useGetRankingQuery({ jobId }, { skip: !isNew });
  const [shortlist, { isLoading: shortlisting }] = useShortlistApplicantsMutation();
  const [selected, setSelected] = useState<string[]>([]);
  const [rejecting, setRejecting] = useState(false);
  const rows = data?.items ?? [];
  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const columns: Column<Applicant>[] = [
    {
      key: "pick",
      header: "",
      render: (item) =>
        TERMINAL_STATUSES.has(item.status) ? null : (
          <span onClick={(e) => e.stopPropagation()}>
            <Checkbox
              label={<span className="sr-only">Select {item.candidate.name}</span>}
              checked={selected.includes(item.application_id)}
              onChange={() => toggle(item.application_id)}
            />
          </span>
        ),
    },
    {
      key: "candidate",
      header: "Student",
      render: (item) => (
        <div className="min-w-0 max-w-[200px]">
          <p className="font-semibold text-slate-900 truncate">{item.candidate.name}</p>
          <p className="text-xs text-slate-500 truncate">{item.candidate.email || "No email"}</p>
          {item.candidate.roll_number && (
            <p className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
              ID: {item.candidate.roll_number}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "job",
      header: "Applied Job & Company",
      hideOnMobile: true,
      render: (item) => (
        <div className="min-w-0 max-w-[200px]">
          <p className="font-medium text-slate-800 text-sm truncate">{item.job_title || "Job"}</p>
          <p className="text-xs text-slate-500 truncate">{item.company_name || "Company"}</p>
        </div>
      ),
    },
    {
      key: "applied_at",
      header: "Applied Date",
      hideOnMobile: true,
      render: (item) => (
        <span className="text-xs text-slate-600 whitespace-nowrap">
          {item.applied_at ? formatDate(item.applied_at) : "—"}
        </span>
      ),
    },
    {
      key: "resume",
      header: "Resume",
      hideOnMobile: true,
      render: (item) =>
        item.resume_version_no > 0 ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
            Available (v{item.resume_version_no})
          </span>
        ) : (
          <span className="text-xs text-slate-400">None</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      render: (item) => <ApplicationStatusBadge status={item.status} />,
    },
    {
      key: "match",
      header: "Match",
      hideOnMobile: true,
      render: (item) => <MatchBadge score={item.match_score} />,
    },
    {
      key: "ai",
      header: "AI Recommendation",
      hideOnMobile: true,
      render: (item) => {
        const s = item.screening.recommendation ? SUGGESTION[item.screening.recommendation] : null;
        return s ? (
          <span className={cn("rounded-full px-2.5 py-1 text-xs font-bold whitespace-nowrap", s.tone)}>
            {s.label}
            {item.screening.score != null ? ` · ${item.screening.score}` : ""}
          </span>
        ) : (
          <span className="text-xs text-slate-400">Not screened</span>
        );
      },
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right whitespace-nowrap",
      render: (item) => (
        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => navigate(`/jobs/employer/applications/${item.application_id}`)}
          >
            View Details
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* Stages Tabs */}
      <div
        role="tablist"
        aria-label="Stage"
        className="flex flex-wrap gap-1 rounded-xl bg-slate-100/80 p-1 ring-1 ring-slate-200/60"
      >
        {allStages.map((s) => (
          <button
            key={s.key}
            type="button"
            role="tab"
            aria-selected={s.key === stage?.key}
            onClick={() => {
              setStageKey(s.key);
              setStatusFilter(undefined);
              setSelected([]);
            }}
            className={cn(
              "h-9 rounded-lg px-3.5 text-sm font-semibold transition-all",
              s.key === stage?.key
                ? "bg-white text-navy-950 shadow-card"
                : "text-slate-600 hover:text-navy-950"
            )}
          >
            {s.label} <span className="ml-1 text-xs text-slate-500 font-normal">({s.count})</span>
          </button>
        ))}
      </div>

      {isNew && ranking && <AiRankingBanner ranking={ranking} onSelect={(ids) => setSelected(ids)} />}

      {/* Filter and Search Bar */}
      <FilterRow>
        <FilterText
          label="Search"
          value={q}
          placeholder="Search by student name or email…"
          onChange={setQ}
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          options={[
            { value: "", label: "All Statuses" },
            { value: "applied", label: "Applied" },
            { value: "ai_screened", label: "AI Screened" },
            { value: "shortlisted", label: "Shortlisted" },
            { value: "assessment_invited", label: "Assessment Invited" },
            { value: "assessment_completed", label: "Assessment Completed" },
            { value: "ai_interview_invited", label: "AI Interview Invited" },
            { value: "ai_interview_completed", label: "AI Interview Completed" },
            { value: "recruiter_review", label: "Recruiter Review" },
            { value: "hr_interview", label: "HR Interview" },
            { value: "offered", label: "Offered" },
            { value: "offer_accepted", label: "Offer Accepted" },
            { value: "placed", label: "Selected / Placed" },
            { value: "rejected", label: "Rejected" },
            { value: "withdrawn", label: "Withdrawn" },
          ]}
          onChange={setStatusFilter}
        />
        <FilterSelect
          label="Sort By"
          value={sortBy}
          options={SORT_OPTIONS}
          onChange={(val) => setSortBy((val as "recent" | "match" | "screen") || "recent")}
        />
      </FilterRow>

      {/* Applicants Table */}
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(item) => item.application_id}
        loading={isFetching}
        onRowClick={(item) => navigate(`/jobs/employer/applications/${item.application_id}`)}
        empty={
          <EmptyState
            icon="users"
            title={`No applicants in ${stage?.label ?? "this stage"}`}
            description="Submitted student applications will appear here."
          />
        }
      />

      {/* Batch Action Toolbar */}
      {selected.length > 0 && (
        <div className="sticky bottom-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white px-4 py-3 shadow-pop ring-1 ring-slate-200">
          <span role="status" className="text-sm text-slate-700">
            <strong>{selected.length}</strong> applicant(s) selected
          </span>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={selected.length === 0}
              onClick={() => setRejecting(true)}
            >
              Not moving forward (Reject)
            </Button>
            <Button
              disabled={selected.length === 0}
              loading={shortlisting}
              onClick={async () => {
                try {
                  const result = await shortlist({ jobId, application_ids: selected }).unwrap();
                  notify.success(`${result.count} shortlisted`);
                  setSelected([]);
                } catch (error) {
                  notify.apiError(error);
                }
              }}
            >
              Shortlist Selected
            </Button>
          </div>
        </div>
      )}

      {rejecting && (
        <RejectDialog
          jobId={jobId}
          ids={selected}
          onClose={(done) => {
            setRejecting(false);
            if (done) setSelected([]);
          }}
        />
      )}
    </div>
  );
}
