import { useParams } from "react-router-dom";

import { useGetBoardJobQuery } from "@/modules/job-portal/board/api/boardApi";
import { ApplyBox } from "@/modules/job-portal/board/components/ApplyBox";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

/** Page for applying to a specific job. */
export function ApplyJobPage() {
  const { jobId = "" } = useParams();
  const { data: job, isLoading, isError } = useGetBoardJobQuery(jobId, { skip: !jobId });

  if (isLoading) return <PageLoader />;
  if (isError || !job) return <EmptyState icon="alert" title="This job isn't available" description="It may have closed. Browse other openings on the job board." />;

  return (
    <>
      <PageHeader title={`Apply to ${job.title}`} description={job.company_name ?? undefined} backTo="/jobs/board" backLabel="Jobs" />
      <div className="mx-auto max-w-3xl">
        <ApplyBox job={job} />
      </div>
    </>
  );
}
