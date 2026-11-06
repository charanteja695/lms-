import { useParams } from "react-router-dom";

import { useGetBoardJobQuery } from "@/modules/job-portal/board/api/boardApi";
import { JobPanel } from "@/modules/job-portal/board/components/JobPanel";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

/** One job on its own page (phones, shared links): the same panel as beside the list. */
export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const { data: job, isLoading, isError } = useGetBoardJobQuery(jobId, { skip: !jobId });
  if (isLoading) return <PageLoader />;
  if (isError || !job) return <EmptyState icon="alert" title="This job isn't available" description="It may have closed. Browse other openings on the job board." />;
  return (
    <>
      <PageHeader title={job.title} description={job.company_name ?? undefined} backTo="/jobs/board" backLabel="Jobs" />
      <div className="mx-auto w-full p-4">
        <JobPanel job={job} />
      </div>
    </>
  );
}
